import pytest

from maritime.core.events.in_memory import InMemoryEventBus
from maritime.core.exceptions import EntityNotFoundError, InvariantViolationError
from maritime.modules.ingestion.application.dtos import UploadFileDto
from maritime.modules.ingestion.application.use_cases import (
    GetDocumentStatusUseCase,
    ListDocumentsUseCase,
    UploadContractsBatchUseCase,
    UploadContractUseCase,
)
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.events import DocumentUploadedEvent
from maritime.modules.ingestion.domain.ports import IDocumentRepository, IFileStorage
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)


class InMemoryDocumentRepository(IDocumentRepository):
    def __init__(self) -> None:
        self.documents: dict[str, ContractDocument] = {}

    async def save(self, document: ContractDocument) -> None:
        self.documents[document.id.value] = document

    async def find_by_id(self, document_id: DocumentId) -> ContractDocument | None:
        return self.documents.get(document_id.value)

    async def find_by_content_hash(self, content_hash: ContentHash) -> ContractDocument | None:
        for doc in self.documents.values():
            if doc.content_hash == content_hash:
                return doc
        return None

    async def list_all(self, status: DocumentStatus | None = None) -> list[ContractDocument]:
        if status is None:
            return list(self.documents.values())
        return [doc for doc in self.documents.values() if doc.status == status]


class InMemoryFileStorage(IFileStorage):
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def save(self, doc_id: str, filename: str, content: bytes) -> str:
        path = f"storage/{doc_id}/{filename}"
        self.files[path] = content
        return path

    async def read(self, file_path: str) -> bytes:
        return self.files[file_path]

    async def exists(self, file_path: str) -> bool:
        return file_path in self.files


@pytest.fixture
def repo() -> InMemoryDocumentRepository:
    return InMemoryDocumentRepository()


@pytest.fixture
def storage() -> InMemoryFileStorage:
    return InMemoryFileStorage()


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_contract_success(
    repo: InMemoryDocumentRepository,
    storage: InMemoryFileStorage,
    event_bus: InMemoryEventBus,
) -> None:
    use_case = UploadContractUseCase(
        document_repository=repo,
        file_storage=storage,
        event_bus=event_bus,
        max_file_size_bytes=26_214_400,
    )
    content = b"%PDF-1.4 contract content"
    filename = "contract_test.pdf"

    doc = await use_case.execute(filename=filename, content=content)

    assert doc.filename == filename
    assert doc.status == DocumentStatus.PENDING
    assert doc.size_bytes == len(content)

    # Repository persisted
    saved = await repo.find_by_id(doc.id)
    assert saved is not None
    assert saved.id == doc.id

    # Storage saved
    assert len(storage.files) == 1

    # Event dispatched to event bus
    assert len(event_bus.published_events) == 1
    event = event_bus.published_events[0]
    assert isinstance(event, DocumentUploadedEvent)
    assert event.document_id == doc.id.value


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_contract_idempotency(
    repo: InMemoryDocumentRepository,
    storage: InMemoryFileStorage,
    event_bus: InMemoryEventBus,
) -> None:
    use_case = UploadContractUseCase(
        document_repository=repo,
        file_storage=storage,
        event_bus=event_bus,
        max_file_size_bytes=26_214_400,
    )
    content = b"%PDF-1.4 duplicate contract"
    filename = "contract_dup.pdf"

    # First upload
    doc1 = await use_case.execute(filename=filename, content=content)
    assert len(repo.documents) == 1
    assert len(event_bus.published_events) == 1

    # Second upload with identical content
    doc2 = await use_case.execute(filename="different_name.pdf", content=content)

    # Must return the same document without creating a duplicate in repo or publishing extra event
    assert doc1.id == doc2.id
    assert len(repo.documents) == 1
    assert len(event_bus.published_events) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_contract_validates_pdf_and_non_empty(
    repo: InMemoryDocumentRepository,
    storage: InMemoryFileStorage,
    event_bus: InMemoryEventBus,
) -> None:
    use_case = UploadContractUseCase(
        document_repository=repo,
        file_storage=storage,
        event_bus=event_bus,
        max_file_size_bytes=26_214_400,
    )

    # Empty content
    with pytest.raises(InvariantViolationError, match="File content cannot be empty"):
        await use_case.execute(filename="test.pdf", content=b"")

    # Non-pdf file extension
    with pytest.raises(InvariantViolationError, match="Only PDF files are supported"):
        await use_case.execute(filename="test.txt", content=b"text content")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_document_status_use_case(
    repo: InMemoryDocumentRepository,
) -> None:
    doc_id = DocumentId.generate()
    doc = ContractDocument.create(
        id=doc_id,
        filename="test.pdf",
        content_hash=ContentHash("a" * 64),
        size_bytes=100,
    )
    await repo.save(doc)

    use_case = GetDocumentStatusUseCase(document_repository=repo)
    result = await use_case.execute(document_id=doc_id.value)

    assert result.document_id == doc_id.value
    assert result.status == DocumentStatus.PENDING
    assert result.filename == "test.pdf"

    from uuid import uuid4

    non_existent_id = str(uuid4())
    with pytest.raises(EntityNotFoundError):
        await use_case.execute(document_id=non_existent_id)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_documents_use_case(
    repo: InMemoryDocumentRepository,
) -> None:
    doc1 = ContractDocument.create(
        id=DocumentId.generate(),
        filename="doc1.pdf",
        content_hash=ContentHash("a" * 64),
        size_bytes=100,
    )
    doc2 = ContractDocument.create(
        id=DocumentId.generate(),
        filename="doc2.pdf",
        content_hash=ContentHash("b" * 64),
        size_bytes=200,
    )
    doc2.mark_as_processing()
    doc2.mark_as_ready(total_chunks=3)

    await repo.save(doc1)
    await repo.save(doc2)

    use_case = ListDocumentsUseCase(document_repository=repo)

    all_docs = await use_case.execute()
    assert len(all_docs) == 2
    assert all_docs[0].created_at is not None

    ready_docs = await use_case.execute(status=DocumentStatus.READY)
    assert len(ready_docs) == 1
    assert ready_docs[0].document_id == doc2.id.value
    assert ready_docs[0].chunk_count == 3


@pytest.fixture
def batch_use_case(
    repo: InMemoryDocumentRepository,
    storage: InMemoryFileStorage,
    event_bus: InMemoryEventBus,
) -> UploadContractsBatchUseCase:
    upload = UploadContractUseCase(
        document_repository=repo,
        file_storage=storage,
        event_bus=event_bus,
        max_file_size_bytes=26_214_400,
    )
    return UploadContractsBatchUseCase(upload_contract=upload)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_batch_upload_isolates_rejected_files_and_keeps_order(
    batch_use_case: UploadContractsBatchUseCase,
    repo: InMemoryDocumentRepository,
) -> None:
    result = await batch_use_case.execute(
        [
            UploadFileDto(filename="a.pdf", content=b"%PDF-1.4 contract a"),
            UploadFileDto(filename="notes.txt", content=b"plain text"),
            UploadFileDto(filename="b.pdf", content=b"%PDF-1.4 contract b"),
            UploadFileDto(filename="a_again.pdf", content=b"%PDF-1.4 contract a"),
        ]
    )

    assert (result.accepted, result.rejected) == (3, 1)
    assert [i.filename for i in result.items] == ["a.pdf", "notes.txt", "b.pdf", "a_again.pdf"]
    assert result.items[1].document is None
    assert result.items[1].error is not None
    assert "Only PDF files are supported" in result.items[1].error
    assert result.items[0].document is not None
    assert result.items[3].document is not None
    assert result.items[0].document.document_id == result.items[3].document.document_id
    assert len(repo.documents) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_batch_upload_rejects_blank_filename_per_file(
    batch_use_case: UploadContractsBatchUseCase,
) -> None:
    result = await batch_use_case.execute(
        [
            UploadFileDto(filename="", content=b"%PDF-1.4 contract"),
            UploadFileDto(filename="ok.pdf", content=b"%PDF-1.4 contract ok"),
        ]
    )

    assert (result.accepted, result.rejected) == (1, 1)
    assert result.items[0].error == "Filename is required."
    assert result.items[1].document is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_batch_upload_requires_at_least_one_file(
    batch_use_case: UploadContractsBatchUseCase,
) -> None:
    with pytest.raises(InvariantViolationError, match="At least one file is required"):
        await batch_use_case.execute([])
