import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from maritime.core.telemetry.logging import get_logger
from maritime.infrastructure.celery.celery_app import celery_app
from maritime.infrastructure.database.session import create_worker_session_factory
from maritime.infrastructure.di.deps import get_container
from maritime.infrastructure.events.deferred import transaction_scope
from maritime.modules.ingestion.domain.value_objects import DocumentId, DocumentStatus
from maritime.modules.ingestion.infrastructure.repository import SqlAlchemyDocumentRepository

logger = get_logger(__name__)

# Session factory dedicated to background worker using NullPool
_worker_session_factory: async_sessionmaker[AsyncSession] = create_worker_session_factory()


def get_worker_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns the session factory used by Celery worker tasks."""
    return _worker_session_factory


def set_worker_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Sets a custom session factory (primarily used for test isolation)."""
    global _worker_session_factory
    _worker_session_factory = factory


STUCK_DOCUMENT_REASON = (
    "El procesamiento no terminó a tiempo (el worker pudo ser interrumpido). "
    "Vuelve a subir el archivo para reintentar."
)


@celery_app.task(name="maritime.fail_stuck_documents")  # type: ignore[untyped-decorator]
def fail_stuck_documents_task() -> list[str]:
    """Reaper: ends documents stuck in PROCESSING with a clear, readable failure reason."""
    factory = get_worker_session_factory()
    timeout = get_container().settings.PROCESSING_TIMEOUT_SECONDS

    async def _run() -> list[str]:
        async with factory() as session:
            repo = SqlAlchemyDocumentRepository(session=session)
            cutoff = datetime.now(UTC) - timedelta(seconds=timeout)
            failed_ids = await repo.fail_stuck_processing(cutoff, STUCK_DOCUMENT_REASON)
            await session.commit()
            return failed_ids

    failed = asyncio.run(_run())
    if failed:
        logger.warning("Marked stuck documents as failed", extra={"documents": failed})
    return failed


@celery_app.task(name="maritime.process_document", bind=True)  # type: ignore[untyped-decorator]
def process_document_task(self: object, document_id: str) -> dict[str, str]:
    """Asynchronous Celery task to parse, chunk, embed, and index a contract document."""
    logger.info("Starting background document processing", extra={"document_id": document_id})

    factory = get_worker_session_factory()
    task_result: dict[str, str] = {"document_id": document_id, "status": "processed"}

    async def _run() -> None:
        container = get_container()
        async with transaction_scope(container.event_bus) as events, factory() as session:
            try:
                use_case = container.get_index_document_use_case(session=session)
                if not await use_case.start(document_id=document_id):
                    return

                # Commit `processing` before the slow work: from now on other processes (the UI,
                # the reaper) can see it, and so does the ProcessingStarted event.
                await session.commit()
                await events.flush()

                await use_case.run(document_id=document_id)
                await session.commit()
                await events.flush()

                # Check if document was marked as failed by use case
                repo = SqlAlchemyDocumentRepository(session=session)
                doc = await repo.find_by_id(DocumentId.from_str(document_id))
                if doc and doc.status == DocumentStatus.FAILED:
                    task_result["status"] = "failed"
                    task_result["error"] = doc.error_detail or "Unknown processing error"
            except Exception:
                await session.rollback()
                raise

    try:
        asyncio.run(_run())
        return task_result
    except Exception as exc:
        exc_msg = str(exc)
        logger.error(
            "Background task failed for document_id=%s: %s",
            document_id,
            exc_msg,
            extra={"document_id": document_id, "error": exc_msg},
        )

        # Fallback: ensure document is never left stuck in PENDING without explanation
        try:

            async def _mark_failed_fallback() -> None:
                bus = get_container().event_bus
                async with transaction_scope(bus) as events, factory() as session:
                    repo = SqlAlchemyDocumentRepository(session=session)
                    doc_id = DocumentId.from_str(document_id)
                    doc = await repo.find_by_id(doc_id)
                    if doc and doc.status != DocumentStatus.READY:
                        doc.mark_as_failed(f"Error en worker: {exc_msg}")
                        await repo.save(doc)
                        await bus.publish_all(doc.pull_events())
                        await session.commit()
                        await events.flush()

            asyncio.run(_mark_failed_fallback())
        except Exception as fallback_exc:
            logger.error(
                "Fallback mark_as_failed failed for document_id=%s: %s",
                document_id,
                fallback_exc,
            )

        return {"document_id": document_id, "status": "failed", "error": exc_msg}
