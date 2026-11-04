"""Integration tests for the idempotent indexing task with real PostgreSQL (pgvector) and Redis.

Covers the failure modes required by the brief: the same PDF uploaded twice, a task that is
redelivered after success, and a task that dies mid-way and is retried. In every case the
database must end with exactly one complete chunk set per document.
"""

import asyncio
import io
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from celery.contrib.testing.worker import start_worker
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from maritime.core.events.event_bus import IEventBus
from maritime.core.events.in_memory import InMemoryEventBus
from maritime.infrastructure.celery.celery_app import celery_app
from maritime.infrastructure.config import Settings
from maritime.infrastructure.database.session import Base, create_worker_session_factory
from maritime.infrastructure.di.container import ApplicationContainer
from maritime.infrastructure.events.deferred import transaction_scope
from maritime.modules.indexing.infrastructure.models import DocumentChunkModel
from maritime.modules.indexing.tasks.celery_tasks import (
    fail_stuck_documents_task,
    get_worker_session_factory,
    process_document_task,
    set_worker_session_factory,
)
from maritime.modules.ingestion.domain.value_objects import DocumentStatus
from maritime.modules.ingestion.infrastructure.models import ContractDocumentModel


def _pdf(text_line: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.drawString(100, 750, "Contrato Naviera Portecho")
    pdf.drawString(100, 720, text_line)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@pytest.fixture(scope="module")
def postgres() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("pgvector/pgvector:pg16") as container:
        yield container


@pytest.fixture(scope="module")
def redis() -> Generator[RedisContainer, None, None]:
    with RedisContainer("redis:7-alpine") as container:
        yield container


class Env:
    """Wires a real database, storage and application container for one test."""

    def __init__(
        self,
        async_url: str,
        storage: Path,
        embedding_failures: int = 0,
        event_bus: IEventBus | None = None,
    ) -> None:
        self.factory: async_sessionmaker[AsyncSession] = create_worker_session_factory(async_url)
        self.container = ApplicationContainer(
            session_factory=self.factory,
            event_bus=event_bus or InMemoryEventBus(),
            settings=Settings(
                DATABASE_URL=async_url, STORAGE_PATH=str(storage), LLM_PROVIDER="mock"
            ),
        )
        self.embedding_failures = embedding_failures

        real_embed = self.container.embedding_service.embed_batch

        def flaky_embed(texts: Any) -> Any:
            if self.embedding_failures > 0:
                self.embedding_failures -= 1
                raise RuntimeError("simulated provider outage / worker killed mid-task")
            return real_embed(texts)

        self.container.embedding_service.embed_batch = flaky_embed  # type: ignore[method-assign]

    async def upload(self, filename: str, content: bytes) -> str:
        async with transaction_scope(self.container.event_bus) as events:
            async with self.factory() as session:
                use_case = self.container.get_upload_contract_use_case(session=session)
                doc = await use_case.execute(filename=filename, content=content)
                await session.commit()
            await events.flush()
            return doc.id.value

    async def counts(self, document_id: str) -> tuple[str, int, int]:
        async with self.factory() as session:
            doc = (
                await session.execute(
                    select(ContractDocumentModel).where(ContractDocumentModel.id == document_id)
                )
            ).scalar_one()
            n_chunks = (
                await session.execute(
                    select(func.count())
                    .select_from(DocumentChunkModel)
                    .where(DocumentChunkModel.document_id == document_id)
                )
            ).scalar_one()
            return str(doc.status), int(doc.chunk_count), int(n_chunks)

    async def total_documents(self) -> int:
        async with self.factory() as session:
            return int(
                (
                    await session.execute(select(func.count()).select_from(ContractDocumentModel))
                ).scalar_one()
            )


@pytest.fixture
def env(postgres: PostgresContainer, tmp_path: Path) -> Generator[Env, None, None]:
    async_url = postgres.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    )

    async def _reset() -> None:
        engine = create_async_engine(async_url)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_reset())
    storage = tmp_path / "contracts"
    storage.mkdir()
    environment = Env(async_url, storage)
    original = get_worker_session_factory()
    set_worker_session_factory(environment.factory)
    with patch(
        "maritime.modules.indexing.tasks.celery_tasks.get_container",
        return_value=environment.container,
    ):
        yield environment
    set_worker_session_factory(original)


@pytest.mark.integration
def test_same_pdf_uploaded_twice_yields_one_document_and_one_chunk_set(env: Env) -> None:
    content = _pdf("Tarifa Base por TEU: 1250 USD")

    first = asyncio.run(env.upload("a.pdf", content))
    second = asyncio.run(env.upload("copy_of_a.pdf", content))
    assert first == second
    assert asyncio.run(env.total_documents()) == 1

    assert process_document_task(first)["status"] == "processed"
    status, chunk_count, rows = asyncio.run(env.counts(first))
    assert status == DocumentStatus.READY
    assert chunk_count == rows > 0

    # Uploading the same bytes again after indexing creates nothing new.
    assert asyncio.run(env.upload("a_again.pdf", content)) == first
    assert asyncio.run(env.total_documents()) == 1
    assert asyncio.run(env.counts(first)) == (DocumentStatus.READY, chunk_count, rows)


@pytest.mark.integration
def test_redelivered_task_after_success_is_a_noop(env: Env) -> None:
    doc_id = asyncio.run(env.upload("a.pdf", _pdf("Plazo de demoras: 10 dias libres")))

    assert process_document_task(doc_id)["status"] == "processed"
    before = asyncio.run(env.counts(doc_id))

    # Celery is at-least-once: the same message can be delivered again.
    assert process_document_task(doc_id)["status"] == "processed"
    assert asyncio.run(env.counts(doc_id)) == before


@pytest.mark.integration
def test_task_that_dies_mid_way_leaves_no_partial_data_and_retry_completes(env: Env) -> None:
    doc_id = asyncio.run(env.upload("a.pdf", _pdf("Recargo por demora: 75 USD por dia")))
    env.embedding_failures = 1

    failed = process_document_task(doc_id)
    assert failed["status"] == "failed"
    status, chunk_count, rows = asyncio.run(env.counts(doc_id))
    assert (status, chunk_count, rows) == (DocumentStatus.FAILED, 0, 0)

    retried = process_document_task(doc_id)
    assert retried["status"] == "processed"
    status, chunk_count, rows = asyncio.run(env.counts(doc_id))
    assert status == DocumentStatus.READY
    assert chunk_count == rows > 0


@pytest.mark.integration
def test_reuploading_a_failed_document_queues_it_again_without_duplicates(env: Env) -> None:
    content = _pdf("Cláusula de cancelación: 50% del flete")
    doc_id = asyncio.run(env.upload("a.pdf", content))
    env.embedding_failures = 1
    assert process_document_task(doc_id)["status"] == "failed"

    # Same bytes again: no new document, but the failed one goes back to the queue.
    assert asyncio.run(env.upload("a_again.pdf", content)) == doc_id
    assert asyncio.run(env.total_documents()) == 1
    status, _, rows = asyncio.run(env.counts(doc_id))
    assert (status, rows) == (DocumentStatus.PENDING, 0)

    assert process_document_task(doc_id)["status"] == "processed"
    status, chunk_count, rows = asyncio.run(env.counts(doc_id))
    assert status == DocumentStatus.READY
    assert chunk_count == rows > 0


@pytest.mark.integration
def test_concurrent_uploads_of_the_same_pdf_resolve_to_one_document(env: Env) -> None:
    content = _pdf("Seguro de carga: deducible 1000 USD")

    async def _race() -> list[str]:
        return list(await asyncio.gather(*(env.upload(f"copy_{i}.pdf", content) for i in range(4))))

    ids = asyncio.run(_race())

    assert len(set(ids)) == 1
    assert asyncio.run(env.total_documents()) == 1


@pytest.mark.integration
def test_reaper_fails_documents_stuck_in_processing_with_a_readable_reason(env: Env) -> None:
    stuck = asyncio.run(env.upload("stuck.pdf", _pdf("Contrato A")))
    recent = asyncio.run(env.upload("recent.pdf", _pdf("Contrato B")))

    async def _simulate_dead_worker() -> None:
        async with env.factory() as session:
            old = datetime.now(UTC) - timedelta(hours=2)
            for doc_id, updated_at in ((stuck, old), (recent, datetime.now(UTC))):
                await session.execute(
                    text(
                        "UPDATE contracts_documents SET status='processing', updated_at=:ts "
                        "WHERE id=:id"
                    ),
                    {"ts": updated_at, "id": doc_id},
                )
            await session.commit()

    asyncio.run(_simulate_dead_worker())

    assert fail_stuck_documents_task() == [stuck]

    async def _detail(doc_id: str) -> tuple[str, str | None]:
        async with env.factory() as session:
            row = (
                await session.execute(
                    select(ContractDocumentModel).where(ContractDocumentModel.id == doc_id)
                )
            ).scalar_one()
            return str(row.status), row.error_detail

    stuck_status, reason = asyncio.run(_detail(stuck))
    assert stuck_status == DocumentStatus.FAILED
    assert reason is not None and "no terminó a tiempo" in reason
    assert asyncio.run(_detail(recent))[0] == DocumentStatus.PROCESSING


@pytest.mark.integration
def test_task_is_consumed_from_a_real_redis_broker(
    env: Env, redis: RedisContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    host, port = redis.get_container_host_ip(), redis.get_exposed_port(6379)
    doc_id = asyncio.run(env.upload("a.pdf", _pdf("Seguro de carga: prima 0,15%")))

    broker_url = f"redis://{host}:{port}/0"

    keys = ("broker_url", "broker_read_url", "broker_write_url")
    original = {k: celery_app.conf[k] for k in keys}
    celery_app.conf.update({k: broker_url for k in keys})
    celery_app._pool = None  # drop the producer pool cached for the compose hostname
    monkeypatch.setenv("TEST_BROKER", broker_url)
    try:
        with start_worker(
            celery_app,
            perform_ping_check=False,
            pool="solo",
            loglevel="WARNING",
            shutdown_timeout=30,
        ):
            # The result backend is irrelevant here: success is observed in PostgreSQL.
            process_document_task.apply_async(args=[doc_id], ignore_result=True)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                status, _, _ = asyncio.run(env.counts(doc_id))
                if status in (DocumentStatus.READY, DocumentStatus.FAILED):
                    break
                time.sleep(0.5)
    finally:
        celery_app.conf.update(original)
        celery_app._pool = None

    status, chunk_count, rows = asyncio.run(env.counts(doc_id))
    assert status == DocumentStatus.READY
    assert chunk_count == rows > 0
