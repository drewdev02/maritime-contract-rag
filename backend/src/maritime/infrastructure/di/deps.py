from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from maritime.core.events.stream import IEventStream
from maritime.infrastructure.config import settings
from maritime.infrastructure.database.session import async_session_factory
from maritime.infrastructure.di.container import ApplicationContainer
from maritime.infrastructure.event_registry import build_event_registry
from maritime.infrastructure.events.deferred import DeferredEventBus
from maritime.infrastructure.events.hub import EventHub
from maritime.infrastructure.events.redis_stream import RedisEventStream
from maritime.infrastructure.events.relay import RelayEventBus
from maritime.modules.indexing.application.queries import GetChunkUseCase
from maritime.modules.ingestion.application.use_cases import (
    GetDocumentFileUseCase,
    GetDocumentStatusUseCase,
    ListDocumentsUseCase,
    UploadContractsBatchUseCase,
    UploadContractUseCase,
)
from maritime.modules.ingestion.domain.events import DocumentUploadedEvent
from maritime.modules.rag.application.use_cases import AskContractQuestionUseCase


def _enqueue_indexing(document_id: str) -> None:
    from maritime.modules.indexing.tasks.celery_tasks import process_document_task

    process_document_task.delay(document_id)


async def _on_document_uploaded(event: DocumentUploadedEvent) -> None:
    """Local subscriber: queues the indexing task (a command) for a document that was uploaded.

    This deliberately does not go through the shared stream: the stream is at-least-once for its
    readers, and a duplicated "queue this" could make two workers process the same document.
    """
    _enqueue_indexing(event.document_id)


def _event_stream() -> IEventStream:
    return RedisEventStream.from_url(
        settings.EVENT_REDIS_URL,
        key=settings.EVENT_STREAM_KEY,
        maxlen=settings.EVENT_STREAM_MAXLEN,
    )


def build_event_hub() -> EventHub | None:
    """The API's reader of the event stream, or None when events are kept in-process only."""
    if settings.EVENT_BUS_BACKEND != "redis":
        return None
    return EventHub(_event_stream)


def build_event_bus() -> DeferredEventBus:
    """Event bus shared by the API and the worker: local subscribers plus the Redis stream."""
    stream_factory = _event_stream if settings.EVENT_BUS_BACKEND == "redis" else None
    relay = RelayEventBus(build_event_registry(), stream_factory)
    relay.subscribe(DocumentUploadedEvent, _on_document_uploaded)
    return DeferredEventBus(relay)


# Shared global event bus and container for the process (API or worker)
_global_event_bus = build_event_bus()

_container = ApplicationContainer(
    session_factory=async_session_factory,
    event_bus=_global_event_bus,
    settings=settings,
)


def get_container() -> ApplicationContainer:
    """Returns the application container singleton."""
    return _container


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a database session with automatic commit/rollback.

    Events raised during the request (including the one that queues the indexing task) are
    published only after a successful commit, so nobody learns about data that is not visible yet.
    """
    async with _global_event_bus.scope() as events:
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        await events.flush()


def get_upload_contract_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> UploadContractUseCase:
    return container.get_upload_contract_use_case(session=session)


def get_upload_contracts_batch_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> UploadContractsBatchUseCase:
    return container.get_upload_contracts_batch_use_case(session=session)


def get_document_status_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> GetDocumentStatusUseCase:
    return container.get_document_status_use_case(session=session)


def get_list_documents_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> ListDocumentsUseCase:
    return container.get_list_documents_use_case(session=session)


def get_document_file_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> GetDocumentFileUseCase:
    return container.get_document_file_use_case(session=session)


def get_chunk_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> GetChunkUseCase:
    return container.get_chunk_use_case(session=session)


def get_ask_contract_question_use_case(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    container: Annotated[ApplicationContainer, Depends(get_container)],
) -> AskContractQuestionUseCase:
    return container.get_ask_contract_question_use_case(session=session)
