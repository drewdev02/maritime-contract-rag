import pytest
from fastapi.testclient import TestClient

from maritime.infrastructure.di.deps import (
    get_document_status_use_case,
    get_list_documents_use_case,
    get_upload_contract_use_case,
    get_upload_contracts_batch_use_case,
)
from maritime.main import app
from maritime.modules.ingestion.application.use_cases import (
    GetDocumentStatusUseCase,
    ListDocumentsUseCase,
    UploadContractsBatchUseCase,
    UploadContractUseCase,
)
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.ports import IDocumentRepository, IFileStorage
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)


class MockDocRepo(IDocumentRepository):
    def __init__(self) -> None:
        self.docs: dict[str, ContractDocument] = {}

    async def save(self, document: ContractDocument) -> None:
        self.docs[document.id.value] = document

    async def find_by_id(self, document_id: DocumentId) -> ContractDocument | None:
        return self.docs.get(document_id.value)

    async def find_by_content_hash(self, content_hash: ContentHash) -> ContractDocument | None:
        for d in self.docs.values():
            if d.content_hash == content_hash:
                return d
        return None

    async def list_all(self, status: DocumentStatus | None = None) -> list[ContractDocument]:
        if status is None:
            return list(self.docs.values())
        return [d for d in self.docs.values() if d.status == status]


class MockStorage(IFileStorage):
    async def save(self, doc_id: str, filename: str, content: bytes) -> str:
        return f"/mock/{doc_id}/{filename}"

    async def read(self, file_path: str) -> bytes:
        return b""

    async def exists(self, file_path: str) -> bool:
        return True


class MockEventBus:
    async def publish_all(self, events: list[object]) -> None:
        pass


@pytest.fixture
def test_client() -> TestClient:
    repo = MockDocRepo()
    storage = MockStorage()
    bus = MockEventBus()

    upload_uc = UploadContractUseCase(
        document_repository=repo,
        file_storage=storage,
        event_bus=bus,  # type: ignore[arg-type]
        max_file_size_bytes=26_214_400,
    )
    status_uc = GetDocumentStatusUseCase(document_repository=repo)
    list_uc = ListDocumentsUseCase(document_repository=repo)

    batch_uc = UploadContractsBatchUseCase(upload_contract=upload_uc)

    app.dependency_overrides[get_upload_contract_use_case] = lambda: upload_uc
    app.dependency_overrides[get_upload_contracts_batch_use_case] = lambda: batch_uc
    app.dependency_overrides[get_document_status_use_case] = lambda: status_uc
    app.dependency_overrides[get_list_documents_use_case] = lambda: list_uc

    client = TestClient(app)
    return client


@pytest.mark.unit
def test_upload_endpoint_success(test_client: TestClient) -> None:
    files = {"file": ("contract_test.pdf", b"%PDF-1.4 maritime dummy", "application/pdf")}
    response = test_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "contract_test.pdf"
    assert data["status"] == "pending"
    assert "document_id" in data


@pytest.mark.unit
def test_upload_endpoint_rejects_non_pdf(test_client: TestClient) -> None:
    files = {"file": ("contract.txt", b"plain text", "text/plain")}
    response = test_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["detail"]


@pytest.mark.unit
def test_get_document_status_404(test_client: TestClient) -> None:
    from uuid import uuid4

    response = test_client.get(f"/api/v1/documents/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.unit
def test_list_documents_endpoint(test_client: TestClient) -> None:
    # First upload a document
    files = {"file": ("sample.pdf", b"%PDF-1.4 maritime sample", "application/pdf")}
    test_client.post("/api/v1/documents/upload", files=files)

    response = test_client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["filename"] == "sample.pdf"


@pytest.mark.unit
def test_batch_upload_reports_each_file_and_does_not_fail_on_one_bad_file(
    test_client: TestClient,
) -> None:
    files = [
        ("files", ("a.pdf", b"%PDF-1.4 contract a", "application/pdf")),
        ("files", ("notes.txt", b"plain text", "text/plain")),
        ("files", ("b.pdf", b"%PDF-1.4 contract b", "application/pdf")),
        ("files", ("a_again.pdf", b"%PDF-1.4 contract a", "application/pdf")),
    ]
    response = test_client.post("/api/v1/documents/upload-batch", files=files)

    assert response.status_code == 200
    data = response.json()
    assert (data["accepted"], data["rejected"]) == (3, 1)
    assert [i["filename"] for i in data["items"]] == ["a.pdf", "notes.txt", "b.pdf", "a_again.pdf"]
    assert data["items"][1]["document"] is None
    assert "Only PDF files are supported" in data["items"][1]["error"]
    # Same bytes uploaded twice resolve to the same document (idempotent).
    assert (
        data["items"][0]["document"]["document_id"] == data["items"][3]["document"]["document_id"]
    )
    assert test_client.get("/api/v1/documents").json()["total"] == 2


@pytest.mark.unit
def test_upload_rejects_file_with_pdf_extension_but_non_pdf_content(
    test_client: TestClient,
) -> None:
    files = {"file": ("fake.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")}
    response = test_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    assert "not a valid PDF" in response.json()["detail"]
