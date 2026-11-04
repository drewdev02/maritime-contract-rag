"""End to end: a worker task publishes to Redis and a browser-like client receives it over SSE.

A real uvicorn server runs the real FastAPI app (lifespan included) against a real Redis; the
worker side is the real Celery task running in this process, as in the other integration tests.
"""

import asyncio
import json
import socket
import threading
import time
from collections.abc import Generator
from typing import Any

import httpx
import pytest
import uvicorn

from maritime.infrastructure.config import settings
from maritime.infrastructure.events.hub import EventHub
from maritime.infrastructure.events.redis_stream import RedisEventStream
from maritime.main import app
from maritime.modules.indexing.tasks.celery_tasks import process_document_task
from tests.integration.test_event_publishing_integration import (  # noqa: F401
    StreamedEnv,
    streamed,
)
from tests.integration.test_idempotency_integration import _pdf, postgres, redis  # noqa: F401


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class SseClient:
    """Reads an SSE response on a thread, collecting ``(id, event, data)`` frames."""

    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self.frames: list[tuple[str, str, dict[str, Any]]] = []
        self.connected = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(url, headers or {}), daemon=True)
        self._thread.start()

    def _run(self, url: str, headers: dict[str, str]) -> None:
        current: dict[str, str] = {}
        try:
            with httpx.stream("GET", url, headers=headers, timeout=httpx.Timeout(30, read=30)) as r:
                for line in r.iter_lines():
                    if self._stop.is_set():
                        return
                    if line.startswith("retry:"):
                        self.connected.set()
                    elif line.startswith(("id:", "event:", "data:")):
                        key, _, value = line.partition(": ")
                        current[key] = value
                    elif line == "" and "event" in current:
                        self.frames.append(
                            (current.get("id", ""), current["event"], json.loads(current["data"]))
                        )
                        current = {}
        except httpx.HTTPError:
            return

    def wait_for(self, count: int, timeout: float = 15) -> list[tuple[str, str, dict[str, Any]]]:
        deadline = time.monotonic() + timeout
        while len(self.frames) < count and time.monotonic() < deadline:
            time.sleep(0.05)
        return list(self.frames)

    def stop(self) -> None:
        self._stop.set()


@pytest.fixture
def api(
    streamed: StreamedEnv,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[str, None, None]:
    monkeypatch.setattr(settings, "EVENT_BUS_BACKEND", "redis")
    monkeypatch.setattr(settings, "EVENT_REDIS_URL", streamed.redis_url)
    monkeypatch.setattr(settings, "EVENT_STREAM_KEY", streamed.key)

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="on",
            timeout_graceful_shutdown=2,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "uvicorn did not start"

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=10)


@pytest.mark.integration
def test_a_worker_run_reaches_a_connected_client_over_sse_in_order(
    streamed: StreamedEnv,  # noqa: F811
    api: str,
) -> None:
    client = SseClient(f"{api}/api/v1/documents/events")
    assert client.connected.wait(10), "SSE connection was not established"

    doc_id = asyncio.run(streamed.env.upload("a.pdf", _pdf("Tarifa Base por TEU: 1250 USD")))
    process_document_task(doc_id)
    frames = client.wait_for(3)
    client.stop()

    assert [f[1] for f in frames] == [
        "document.uploaded",
        "document.processing_started",
        "document.ready",
    ]
    assert {f[2]["document_id"] for f in frames} == {doc_id}
    assert frames[-1][2]["chunk_count"] > 0
    ids = [f[0] for f in frames]
    assert ids == sorted(ids, key=lambda i: tuple(map(int, i.split("-"))))


@pytest.mark.integration
def test_a_client_that_reconnects_with_last_event_id_is_replayed_what_it_missed(
    streamed: StreamedEnv,  # noqa: F811
    api: str,
) -> None:
    first = SseClient(f"{api}/api/v1/documents/events")
    assert first.connected.wait(10)
    doc_id = asyncio.run(streamed.env.upload("a.pdf", _pdf("Seguro de carga: prima 0,15%")))
    seen = first.wait_for(1)
    first.stop()
    last_seen = seen[0][0]

    process_document_task(doc_id)  # happens while nobody is connected

    second = SseClient(f"{api}/api/v1/documents/events", headers={"Last-Event-ID": last_seen})
    frames = second.wait_for(2)
    second.stop()

    assert [f[1] for f in frames[:2]] == ["document.processing_started", "document.ready"]


@pytest.mark.integration
def test_two_api_instances_each_deliver_every_event_to_their_own_clients(
    streamed: StreamedEnv,  # noqa: F811
) -> None:
    """Fan-out across replicas: each consumer reads the whole stream independently."""

    async def scenario() -> tuple[list[str], list[str]]:
        hubs = [
            EventHub(lambda: RedisEventStream.from_url(streamed.redis_url, key=streamed.key))
            for _ in range(2)
        ]
        for hub in hubs:
            await hub.start()
        try:
            with hubs[0].broadcaster.subscribe() as a, hubs[1].broadcaster.subscribe() as b:
                await asyncio.to_thread(_publish_in_worker, streamed)
                got: list[list[str]] = []
                for sub in (a, b):
                    types = []
                    for _ in range(3):
                        item = await asyncio.wait_for(sub.queue.get(), 10)
                        assert item is not None
                        types.append(item.envelope.type)
                    got.append(types)
                return got[0], got[1]
        finally:
            for hub in hubs:
                await hub.stop()

    first, second = asyncio.run(scenario())

    expected = ["document.uploaded", "document.processing_started", "document.ready"]
    assert first == second == expected


def _publish_in_worker(stack: StreamedEnv) -> None:
    doc_id = asyncio.run(stack.env.upload("b.pdf", _pdf("Plazo de demoras: 10 dias libres")))
    process_document_task(doc_id)


@pytest.mark.integration
def test_the_endpoint_answers_503_when_events_are_not_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "EVENT_BUS_BACKEND", "memory")
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="on",
            timeout_graceful_shutdown=2,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        response = httpx.get(f"http://127.0.0.1:{port}/api/v1/documents/events", timeout=10)
        assert response.status_code == 503
        assert "eventos" in response.json()["detail"]
    finally:
        server.should_exit = True
        thread.join(timeout=10)
