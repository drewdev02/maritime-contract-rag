import pytest

from maritime.core.events.in_memory import InMemoryEventBus
from maritime.modules.indexing.application.use_cases import IndexDocumentUseCase
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.events import (
    DocumentFailedEvent,
    DocumentProcessingStartedEvent,
    DocumentReadyEvent,
)
from maritime.modules.ingestion.domain.value_objects import ContentHash, DocumentId
from tests.unit.indexing.test_index_document_use_case import (
    DummyChunker,
    DummyEmbedding,
    DummyParser,
    InMemoryChunkRepository,
    InMemoryDocumentRepo,
    InMemoryStorage,
)


async def _setup(
    parser: DummyParser | None = None,
) -> tuple[IndexDocumentUseCase, InMemoryEventBus, str]:
    doc_repo, storage, bus = InMemoryDocumentRepo(), InMemoryStorage(), InMemoryEventBus()
    doc_id = DocumentId.generate()
    doc = ContractDocument.create(
        id=doc_id, filename="a.pdf", content_hash=ContentHash("c" * 64), size_bytes=10
    )
    doc.pull_events()  # a document loaded from the database has no pending events
    await doc_repo.save(doc)
    await storage.save(doc_id.value, doc.filename, b"%PDF-1.4 dummy")
    use_case = IndexDocumentUseCase(
        document_repository=doc_repo,
        chunk_repository=InMemoryChunkRepository(),
        file_storage=storage,
        pdf_parser=parser or DummyParser(),
        chunking_service=DummyChunker(),
        embedding_service=DummyEmbedding(),
        event_bus=bus,
    )
    return use_case, bus, doc_id.value


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_successful_run_publishes_started_then_ready_with_the_chunk_count() -> None:
    use_case, bus, doc_id = await _setup()

    await use_case.execute(doc_id)

    assert bus.published_events[0] == DocumentProcessingStartedEvent(
        event_id=bus.published_events[0].event_id,
        occurred_at=bus.published_events[0].occurred_at,
        document_id=doc_id,
    )
    ready = bus.published_events[1]
    assert isinstance(ready, DocumentReadyEvent)
    assert (ready.document_id, ready.chunk_count) == (doc_id, 1)
    assert len(bus.published_events) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_failed_run_publishes_started_then_failed_with_the_readable_reason() -> None:
    use_case, bus, doc_id = await _setup(DummyParser(should_fail_pw=True))

    await use_case.execute(doc_id)

    started, failed = bus.published_events
    assert isinstance(started, DocumentProcessingStartedEvent)
    assert isinstance(failed, DocumentFailedEvent)
    assert failed.reason == "El documento está protegido por contraseña"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_announces_processing_before_any_work_and_run_does_the_rest() -> None:
    use_case, bus, doc_id = await _setup()

    assert await use_case.start(doc_id) is True
    assert [type(e) for e in bus.published_events] == [DocumentProcessingStartedEvent]

    await use_case.run(doc_id)
    assert [type(e) for e in bus.published_events] == [
        DocumentProcessingStartedEvent,
        DocumentReadyEvent,
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_an_already_indexed_document_publishes_nothing_and_is_not_started_again() -> None:
    use_case, bus, doc_id = await _setup()
    await use_case.execute(doc_id)
    bus.clear_history()

    assert await use_case.start(doc_id) is False

    assert bus.published_events == []
