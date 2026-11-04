"""The worker announces what happens to a document on the Redis event stream.

Real PostgreSQL and Redis. These tests also pin down that ``processing`` is committed (visible to
other connections) while the slow work runs, which is what makes the event, the UI and the reaper
truthful.
"""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from maritime.core.events.stream import START_OF_STREAM, IEventStream, StreamEntry
from maritime.infrastructure.database.session import Base
from maritime.infrastructure.event_registry import build_event_registry
from maritime.infrastructure.events.deferred import DeferredEventBus
from maritime.infrastructure.events.redis_stream import RedisEventStream
from maritime.infrastructure.events.relay import RelayEventBus
from maritime.modules.indexing.tasks.celery_tasks import (
    get_worker_session_factory,
    process_document_task,
    set_worker_session_factory,
)
from tests.integration.test_idempotency_integration import (  # noqa: F401
    Env,
    _pdf,
    postgres,
    redis,
)


class StreamedEnv:
    """An ``Env`` whose bus really publishes to a Redis stream."""

    def __init__(
        self, env: Env, stream_factory: Any, sync_url: str, redis_url: str, key: str
    ) -> None:
        self.env = env
        self.stream_factory = stream_factory
        self.sync_url = sync_url
        self.redis_url = redis_url
        self.key = key

    def entries(self) -> list[StreamEntry]:
        async def _read() -> list[StreamEntry]:
            stream: IEventStream = self.stream_factory()
            try:
                return await stream.replay(START_OF_STREAM)
            finally:
                await stream.close()

        return asyncio.run(_read())

    def event_types(self) -> list[str]:
        return [e.envelope.type for e in self.entries() if e.envelope]

    def db_status(self, document_id: str) -> str:
        with psycopg.connect(self.sync_url) as conn:
            row = conn.execute(
                "SELECT status FROM contracts_documents WHERE id = %s", (document_id,)
            ).fetchone()
        assert row is not None
        return str(row[0])


@pytest.fixture
def streamed(
    postgres: PostgresContainer,  # noqa: F811
    redis: RedisContainer,  # noqa: F811
    tmp_path: Path,
) -> Generator[StreamedEnv, None, None]:
    pg_url = postgres.get_connection_url()
    async_url = pg_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    sync_url = pg_url.replace("postgresql+psycopg2://", "postgresql://")

    async def _reset() -> None:
        engine = create_async_engine(async_url)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_reset())

    key = f"test:events:{datetime.now(UTC).timestamp()}"
    redis_url = f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/2"

    def stream_factory() -> IEventStream:
        return RedisEventStream.from_url(redis_url, key=key, maxlen=1000)

    bus = DeferredEventBus(RelayEventBus(build_event_registry(), stream_factory))
    storage = tmp_path / "contracts"
    storage.mkdir()
    env = Env(async_url, storage, event_bus=bus)

    original = get_worker_session_factory()
    set_worker_session_factory(env.factory)
    with patch(
        "maritime.modules.indexing.tasks.celery_tasks.get_container",
        return_value=env.container,
    ):
        yield StreamedEnv(env, stream_factory, sync_url, redis_url, key)
    set_worker_session_factory(original)


@pytest.mark.integration
def test_a_successful_run_publishes_uploaded_started_and_ready_in_order(
    streamed: StreamedEnv,
) -> None:
    doc_id = asyncio.run(streamed.env.upload("a.pdf", _pdf("Tarifa Base por TEU: 1250 USD")))

    assert process_document_task(doc_id)["status"] == "processed"

    assert streamed.event_types() == [
        "document.uploaded",
        "document.processing_started",
        "document.ready",
    ]
    ready = streamed.entries()[-1].envelope
    assert ready is not None
    chunk_count = asyncio.run(streamed.env.counts(doc_id))[1]
    assert ready.payload == {"document_id": doc_id, "chunk_count": chunk_count}


@pytest.mark.integration
def test_processing_is_committed_and_visible_while_the_work_runs(streamed: StreamedEnv) -> None:
    doc_id = asyncio.run(streamed.env.upload("a.pdf", _pdf("Seguro de carga: prima 0,15%")))
    observed: list[str] = []
    real_embed = streamed.env.container.embedding_service.embed_batch

    def spying_embed(texts: Any) -> Any:
        # Runs in the middle of the task, before the final commit, from a separate connection.
        observed.append(streamed.db_status(doc_id))
        return real_embed(texts)

    streamed.env.container.embedding_service.embed_batch = spying_embed  # type: ignore[method-assign]

    process_document_task(doc_id)

    assert observed == ["processing"]
    assert streamed.db_status(doc_id) == "ready"


@pytest.mark.integration
def test_a_failed_run_publishes_failed_with_a_readable_reason(streamed: StreamedEnv) -> None:
    doc_id = asyncio.run(streamed.env.upload("a.pdf", _pdf("Recargo por demora: 75 USD")))
    streamed.env.embedding_failures = 1

    assert process_document_task(doc_id)["status"] == "failed"

    assert streamed.event_types() == [
        "document.uploaded",
        "document.processing_started",
        "document.failed",
    ]
    failed = streamed.entries()[-1].envelope
    assert failed is not None
    assert failed.payload["document_id"] == doc_id
    assert failed.payload["reason"]
    assert "simulated" not in failed.payload["reason"]


@pytest.mark.integration
def test_a_redelivered_task_on_a_ready_document_publishes_nothing_new(
    streamed: StreamedEnv,
) -> None:
    doc_id = asyncio.run(streamed.env.upload("a.pdf", _pdf("Plazo de demoras: 10 dias")))
    process_document_task(doc_id)
    before = streamed.event_types()

    assert process_document_task(doc_id)["status"] == "processed"

    assert streamed.event_types() == before


@pytest.mark.integration
def test_the_stream_being_down_does_not_fail_the_task(streamed: StreamedEnv) -> None:
    doc_id = asyncio.run(streamed.env.upload("a.pdf", _pdf("Cancelación: 50% del flete")))

    def broken_factory() -> IEventStream:
        return RedisEventStream.from_url("redis://127.0.0.1:1/2", key="unreachable")

    bus = streamed.env.container.event_bus
    assert isinstance(bus, DeferredEventBus)
    relay = bus._inner
    assert isinstance(relay, RelayEventBus)
    relay._stream_factory = broken_factory

    assert process_document_task(doc_id)["status"] == "processed"
    assert streamed.db_status(doc_id) == "ready"
