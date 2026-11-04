"""End-to-end latency benchmark against a running stack (docker compose).

Measures, with the sample contracts in ``eval/contracts``:

* ingestion: wall time from upload to ``ready`` for each document, reported per page;
* query: latency of ``POST /api/v1/query`` (sequential and with a few concurrent clients),
  reported as p50, p95 and p99.

Documents are deduplicated by content hash, so by default each upload gets a harmless trailing PDF
comment that changes its hash; otherwise a second run would just return the existing documents.

Usage (from ``backend/``, with the stack up)::

    uv run python eval/benchmark.py --base-url http://localhost:8000
"""

import argparse
import io
import json
import math
import statistics
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pypdf import PdfReader

EVAL_DIR = Path(__file__).parent
API = "/api/v1"


def _request(url: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=120) as response:
        body: bytes = response.read()
        return body


def _upload(base: str, name: str, content: bytes) -> dict[str, object]:
    boundary = uuid.uuid4().hex
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    raw = _request(
        f"{base}{API}/documents/upload",
        body,
        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    parsed: dict[str, object] = json.loads(raw)
    return parsed


def _status(base: str, document_id: str) -> dict[str, object]:
    parsed: dict[str, object] = json.loads(_request(f"{base}{API}/documents/{document_id}"))
    return parsed


def _query(base: str, question: str) -> float:
    payload = json.dumps({"query": question}).encode()
    start = time.perf_counter()
    _request(f"{base}{API}/query", payload, {"Content-Type": "application/json"})
    return (time.perf_counter() - start) * 1000


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(pct / 100 * len(ordered)) - 1)]


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "n": len(values),
        "p50_ms": round(statistics.median(values), 1),
        "p95_ms": round(percentile(values, 95), 1),
        "p99_ms": round(percentile(values, 99), 1),
        "max_ms": round(max(values), 1),
    }


def bench_ingestion(base: str, rounds: int, unique: bool) -> dict[str, object]:
    per_page: list[float] = []
    per_doc: list[float] = []
    pages_total = 0
    for _ in range(rounds):
        for pdf in sorted((EVAL_DIR / "contracts").glob("*.pdf")):
            content = pdf.read_bytes()
            pages = len(PdfReader(io.BytesIO(content)).pages)
            if unique:
                content += f"\n%bench-{uuid.uuid4().hex}\n".encode()
            start = time.perf_counter()
            doc = _upload(base, pdf.name, content)
            document_id = str(doc["document_id"])
            while True:
                status = _status(base, document_id)
                if status["status"] in ("ready", "failed"):
                    break
                time.sleep(0.05)
            elapsed = time.perf_counter() - start
            if status["status"] != "ready":
                raise SystemExit(f"{pdf.name} ended {status['status']}: {status['error_detail']}")
            per_doc.append(elapsed * 1000)
            per_page.append(elapsed * 1000 / pages)
            pages_total += pages
    return {
        "documents": len(per_doc),
        "pages": pages_total,
        "per_document_ms": summarize(per_doc),
        "per_page_ms": summarize(per_page),
    }


def bench_queries(base: str, requests: int, concurrency: int) -> dict[str, float]:
    questions = [q["question"] for q in json.loads((EVAL_DIR / "qa.json").read_text("utf-8"))]
    workload = [questions[i % len(questions)] for i in range(requests)]
    if concurrency == 1:
        return summarize([_query(base, q) for q in workload])
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        return summarize(list(pool.map(lambda q: _query(base, q), workload)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--ingest-rounds", type=int, default=3, help="passes over the sample PDFs")
    ap.add_argument("--queries", type=int, default=150, help="requests per query scenario")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--no-unique", action="store_true", help="do not alter PDF bytes")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    ingestion = bench_ingestion(base, args.ingest_rounds, unique=not args.no_unique)
    for question in range(5):  # warm-up, discarded
        _query(base, f"calentamiento {question}")
    result = {
        "ingestion": ingestion,
        "query_sequential": bench_queries(base, args.queries, 1),
        f"query_{args.concurrency}_concurrent": bench_queries(base, args.queries, args.concurrency),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
