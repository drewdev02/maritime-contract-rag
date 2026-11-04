import pytest

from maritime.core.exceptions import InvalidStateTransitionError, InvariantViolationError
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.events import (
    DocumentFailedEvent,
    DocumentUploadedEvent,
)
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)


@pytest.fixture
def sample_doc_id() -> DocumentId:
    return DocumentId.generate()


@pytest.fixture
def sample_hash() -> ContentHash:
    return ContentHash("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")


@pytest.mark.unit
def test_create_contract_document(sample_doc_id: DocumentId, sample_hash: ContentHash) -> None:
    doc = ContractDocument.create(
        id=sample_doc_id,
        filename="contract_maersk.pdf",
        content_hash=sample_hash,
        size_bytes=1024,
    )
    assert doc.id == sample_doc_id
    assert doc.filename == "contract_maersk.pdf"
    assert doc.content_hash == sample_hash
    assert doc.size_bytes == 1024
    assert doc.status == DocumentStatus.PENDING
    assert doc.chunk_count == 0
    assert doc.error_detail is None

    events = doc.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], DocumentUploadedEvent)
    assert events[0].document_id == sample_doc_id.value
    assert events[0].content_hash == sample_hash.value
    assert events[0].filename == "contract_maersk.pdf"


@pytest.mark.unit
def test_mark_as_processing(sample_doc_id: DocumentId, sample_hash: ContentHash) -> None:
    doc = ContractDocument.create(
        id=sample_doc_id,
        filename="contract.pdf",
        content_hash=sample_hash,
        size_bytes=500,
    )
    doc.mark_as_processing()
    assert doc.status == DocumentStatus.PROCESSING


@pytest.mark.unit
def test_mark_as_processing_when_ready_raises_error(
    sample_doc_id: DocumentId, sample_hash: ContentHash
) -> None:
    doc = ContractDocument.create(
        id=sample_doc_id,
        filename="contract.pdf",
        content_hash=sample_hash,
        size_bytes=500,
    )
    doc.mark_as_processing()
    doc.mark_as_ready(total_chunks=5)
    assert doc.status == DocumentStatus.READY

    with pytest.raises(InvalidStateTransitionError):
        doc.mark_as_processing()


@pytest.mark.unit
def test_mark_as_ready_success_and_zero_chunks_validation(
    sample_doc_id: DocumentId, sample_hash: ContentHash
) -> None:
    doc = ContractDocument.create(
        id=sample_doc_id,
        filename="contract.pdf",
        content_hash=sample_hash,
        size_bytes=500,
    )
    doc.mark_as_processing()

    with pytest.raises(InvariantViolationError, match="must have at least one chunk"):
        doc.mark_as_ready(total_chunks=0)

    doc.mark_as_ready(total_chunks=8)
    assert doc.status == DocumentStatus.READY
    assert doc.chunk_count == 8


@pytest.mark.unit
def test_mark_as_failed_records_event(sample_doc_id: DocumentId, sample_hash: ContentHash) -> None:
    doc = ContractDocument.create(
        id=sample_doc_id,
        filename="contract.pdf",
        content_hash=sample_hash,
        size_bytes=500,
    )
    _ = doc.pull_events()  # discard initial upload event

    doc.mark_as_failed("PDF is corrupted or password-protected.")
    assert doc.status == DocumentStatus.FAILED
    assert doc.error_detail == "PDF is corrupted or password-protected."

    events = doc.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], DocumentFailedEvent)
    assert events[0].document_id == sample_doc_id.value
    assert events[0].reason == "PDF is corrupted or password-protected."
