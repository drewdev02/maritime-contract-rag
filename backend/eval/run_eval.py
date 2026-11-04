"""Offline retrieval evaluation: hit rate@k and abstention over the synthetic contracts.

Runs the real parser and chunker plus the configured embedding adapter (mock by default,
so no API keys or database are needed) and ranks chunks by cosine similarity in memory.
A question is a *hit@k* when one of the top-k chunks comes from the expected document and
page and contains the expected text. Unanswerable questions (``document: null``) measure
abstention: they pass when the best chunk similarity is below the production threshold.

Usage (from ``backend/``)::

    uv run python eval/run_eval.py [--chunk-chars 500 --overlap 80 --threshold 0.25 --min-hit-rate-at-5 0.9]
"""

import argparse
import json
import math
import statistics
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from maritime.modules.indexing.domain.ports import IEmbeddingService
from maritime.modules.indexing.infrastructure.embeddings.mock_embedding import (
    MockDeterministicEmbeddingAdapter,
)
from maritime.modules.indexing.infrastructure.parsers.pdfplumber_parser import PdfplumberParser
from maritime.modules.indexing.infrastructure.services.markdown_table_chunker import (
    MarkdownTableChunker,
)

EVAL_DIR = Path(__file__).parent
KS = (1, 3, 5)


@dataclass(frozen=True)
class IndexedChunk:
    document: str
    page: int
    text: str
    vector: list[float]


def _fold(text: str) -> str:
    """Lowercase and strip accents so expected strings match regardless of diacritics."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def build_index(
    embedder: IEmbeddingService, chunk_chars: int, overlap: int
) -> tuple[list[IndexedChunk], dict[str, float]]:
    parser = PdfplumberParser()
    chunker = MarkdownTableChunker(max_chunk_chars=chunk_chars, overlap_chars=overlap)
    index: list[IndexedChunk] = []
    ingest_seconds_per_page: dict[str, float] = {}
    for pdf_path in sorted((EVAL_DIR / "contracts").glob("*.pdf")):
        start = time.perf_counter()
        pages = parser.parse(pdf_path.read_bytes())
        chunks = chunker.chunk(pages, document_id=pdf_path.stem)
        vectors = embedder.embed_batch([c.text for c in chunks])
        elapsed = time.perf_counter() - start
        ingest_seconds_per_page[pdf_path.name] = elapsed / max(len(pages), 1)
        for chunk, vector in zip(chunks, vectors, strict=True):
            index.append(IndexedChunk(pdf_path.name, chunk.page_number.value, chunk.text, vector))
    return index, ingest_seconds_per_page


def evaluate(
    embedder: IEmbeddingService, index: list[IndexedChunk], threshold: float
) -> dict[str, object]:
    questions = json.loads((EVAL_DIR / "qa.json").read_text(encoding="utf-8"))
    answerable = [q for q in questions if q["document"]]
    unanswerable = [q for q in questions if not q["document"]]

    hits = dict.fromkeys(KS, 0)
    latencies_ms: list[float] = []
    misses: list[str] = []
    for q in answerable:
        start = time.perf_counter()
        qv = embedder.embed_text(q["question"])
        ranked = sorted(index, key=lambda c: _cosine(qv, c.vector), reverse=True)
        latencies_ms.append((time.perf_counter() - start) * 1000)
        for k in KS:
            if any(
                c.document == q["document"]
                and c.page == q["page"]
                and _fold(q["must_contain"]) in _fold(c.text)
                for c in ranked[:k]
            ):
                hits[k] += 1
        if not any(
            c.document == q["document"] and _fold(q["must_contain"]) in _fold(c.text)
            for c in ranked[: KS[-1]]
        ):
            misses.append(q["id"])

    abstained = 0
    for q in unanswerable:
        qv = embedder.embed_text(q["question"])
        best = max(_cosine(qv, c.vector) for c in index)
        if best < threshold:
            abstained += 1

    latencies_ms.sort()
    p95 = latencies_ms[max(0, math.ceil(0.95 * len(latencies_ms)) - 1)] if latencies_ms else 0.0
    return {
        "chunks": len(index),
        "answerable": len(answerable),
        "hit_rate": {f"@{k}": round(hits[k] / len(answerable), 3) for k in KS},
        "abstention_rate": round(abstained / len(unanswerable), 3) if unanswerable else None,
        "retrieval_ms_p50": round(statistics.median(latencies_ms), 2) if latencies_ms else 0.0,
        "retrieval_ms_p95": round(p95, 2),
        "missed_at_5": misses,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # Same defaults as the application (CHUNK_MAX_CHARS / CHUNK_OVERLAP_CHARS).
    ap.add_argument("--chunk-chars", type=int, default=500)
    ap.add_argument("--overlap", type=int, default=80)
    ap.add_argument("--threshold", type=float, default=0.25)
    ap.add_argument("--min-hit-rate-at-5", type=float, default=0.0, help="exit 1 if below")
    args = ap.parse_args()

    embedder = MockDeterministicEmbeddingAdapter()
    index, per_page = build_index(embedder, args.chunk_chars, args.overlap)
    result = evaluate(embedder, index, args.threshold)
    result["ingest_seconds_per_page"] = round(statistics.mean(per_page.values()), 4)
    result["config"] = {
        "chunk_chars": args.chunk_chars,
        "overlap": args.overlap,
        "threshold": args.threshold,
        "embedder": "mock-deterministic",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["hit_rate"]["@5"] < args.min_hit_rate_at_5:  # type: ignore[index]
        raise SystemExit(1)


if __name__ == "__main__":
    main()
