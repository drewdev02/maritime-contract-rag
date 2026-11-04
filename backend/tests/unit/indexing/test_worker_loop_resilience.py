from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from maritime.core.events.in_memory import InMemoryEventBus
from maritime.infrastructure.database.session import (
    create_engine,
    create_worker_session_factory,
)
from maritime.modules.indexing.tasks.celery_tasks import (
    get_worker_session_factory,
    process_document_task,
    set_worker_session_factory,
)
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)


@pytest.mark.unit
def test_worker_engine_uses_nullpool() -> None:
    """Verifies that the background worker engine explicitly uses NullPool.

    QueuePool reuses open connections across tasks within the same process.
    Because Celery prefork workers invoke asyncio.run() per task, QueuePool causes
    'Task got Future attached to a different loop'. NullPool guarantees fresh connections
    bound only to the active event loop.
    """
    default_engine = create_engine("postgresql+asyncpg://user:pass@localhost:5432/test_db")
    assert isinstance(default_engine.pool, AsyncAdaptedQueuePool)
    default_engine.sync_engine.dispose()

    worker_factory = create_worker_session_factory(
        "postgresql+asyncpg://user:pass@localhost:5432/test_db"
    )
    bind_engine = worker_factory.kw["bind"]
    assert isinstance(bind_engine.sync_engine.pool, NullPool)
    bind_engine.sync_engine.dispose()


@pytest.mark.unit
def test_nullpool_does_not_retain_connections_across_runs() -> None:
    """Verifies that NullPool is configured on the worker engine.

    This ensures that when an asyncio event loop terminates, no stale connection
    bound to the dead loop remains cached for subsequent tasks.
    """
    engine = create_engine(
        "postgresql+asyncpg://user:pass@localhost:5432/test_db",
        poolclass=NullPool,
    )
    assert isinstance(engine.sync_engine.pool, NullPool)
    assert engine.sync_engine.pool.status() == "NullPool"
    engine.sync_engine.dispose()


@pytest.mark.unit
def test_process_document_task_consecutive_executions() -> None:
    """Verifies that process_document_task can run sequentially in the same process

    without crashing due to closed event loop reuse.
    """
    original_factory = get_worker_session_factory()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.get = AsyncMock(return_value=None)
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_factory.return_value.__aexit__.return_value = None

    set_worker_session_factory(mock_factory)

    try:
        mock_container = MagicMock()
        mock_use_case = MagicMock()
        mock_use_case.start = AsyncMock(return_value=True)
        mock_use_case.run = AsyncMock(return_value=None)
        mock_container.get_index_document_use_case.return_value = mock_use_case

        doc1_id = str(DocumentId.generate())
        doc2_id = str(DocumentId.generate())

        with patch(
            "maritime.modules.indexing.tasks.celery_tasks.get_container",
            return_value=mock_container,
        ):
            # Task 1 execution in asyncio.run()
            res1 = process_document_task(document_id=doc1_id)
            assert res1["status"] == "processed"
            assert res1["document_id"] == doc1_id

            # Task 2 execution in a new asyncio.run() in the exact same process
            res2 = process_document_task(document_id=doc2_id)
            assert res2["status"] == "processed"
            assert res2["document_id"] == doc2_id

            assert mock_use_case.start.call_count == 2
            assert mock_use_case.run.call_count == 2
            # `processing` is committed before the slow work, and again once it is done.
            assert mock_session.commit.await_count == 4
    finally:
        set_worker_session_factory(original_factory)


@pytest.mark.unit
def test_process_document_task_fallback_marks_failed_on_exception() -> None:
    """Verifies that if an unexpected exception occurs during processing,

    the fallback handler guarantees the document is transitioned to FAILED and never
    left stuck indefinitely in PENDING.
    """
    original_factory = get_worker_session_factory()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.get = AsyncMock(return_value=None)
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_factory.return_value.__aexit__.return_value = None

    set_worker_session_factory(mock_factory)

    # Prepare document in PENDING status
    doc_id = DocumentId.generate()
    doc = ContractDocument.create(
        id=doc_id,
        filename="contrato_fallido.pdf",
        content_hash=ContentHash("a" * 64),
        size_bytes=1024,
    )
    assert str(doc.status) == "pending"

    try:
        mock_container = MagicMock()
        mock_use_case = MagicMock()
        mock_use_case.start = AsyncMock(
            side_effect=RuntimeError("Parsing error: Corrupted PDF streams")
        )
        mock_container.get_index_document_use_case.return_value = mock_use_case
        event_bus = InMemoryEventBus()
        mock_container.event_bus = event_bus

        with (
            patch(
                "maritime.modules.indexing.tasks.celery_tasks.get_container",
                return_value=mock_container,
            ),
            patch(
                "maritime.modules.indexing.tasks.celery_tasks.SqlAlchemyDocumentRepository"
            ) as mock_repo_cls,
        ):
            mock_repo = MagicMock()
            mock_repo.find_by_id = AsyncMock(return_value=doc)
            mock_repo.save = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            result = process_document_task(document_id=str(doc_id))

            assert result["status"] == "failed"
            assert "Parsing error: Corrupted PDF streams" in result["error"]

            # Verify document state was updated to FAILED and saved
            assert doc.status == DocumentStatus.FAILED
            assert doc.error_detail is not None
            assert "Parsing error: Corrupted PDF streams" in doc.error_detail
            mock_repo.save.assert_awaited_once_with(doc)

            # The failure is announced, so other processes can react to it.
            # (The test document was built with create(), so its Uploaded event is still pending.)
            assert type(event_bus.published_events[-1]).__name__ == "DocumentFailedEvent"
    finally:
        set_worker_session_factory(original_factory)
