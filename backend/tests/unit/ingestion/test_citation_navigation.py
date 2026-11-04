from collections.abc import Generator, Sequence

import pytest
from fastapi.testclient import TestClient

from maritime.infrastructure.di.deps import get_chunk_use_case, get_document_file_use_case
from maritime.main import app
from maritime.modules.indexing.application.queries import GetChunkUseCase
from maritime.modules.indexing.domain.entities import DocumentChunk
from maritime.modules.indexing.domain.ports import IChunkRepository
from maritime.modules.indexing.domain.value_objects import ChunkId, PageNumber, TextSpan
from maritime.modules.ingestion.application.use_cases import GetDocumentFileUseCase
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.ports import IDocumentRepository, IFileStorage
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)

DOC_ID = "11111111-1111-4111-8111-111111111111"
CHUNK_ID = "22222222-2222-4222-8222-222222222222"
PDF_BYTES = b"%PDF-1.4 original contract"


class FakeChunkRepo(IChunkRepository):
    async def save_chunks(self, chunks: Sequence[DocumentChunk]) -> None: ...

    async def delete_by_document_id(self, document_id: DocumentId) -> None: ...

    async def search_similar(
        self, query_embedding: list[float], top_k: int = 5, document_id: DocumentId | None = None
    ) -> list[tuple[DocumentChunk, float]]:
        return []

    async def find_by_document_id(self, document_id: DocumentId) -> list[DocumentChunk]:
        if document_id.value != DOC_ID:
            return []
        return [
            DocumentChunk(
                id=ChunkId(CHUNK_ID),
                document_id=DocumentId(DOC_ID),
                chunk_index=3,
                page_number=PageNumber(2),
                text="Cláusula 4. Días libres: 7 días libres en terminal.",
                span=TextSpan(10, 62),
            )
        ]


class FakeDocRepo(IDocumentRepository):
    async def save(self, document: ContractDocument) -> None: ...

    async def find_by_id(self, document_id: DocumentId) -> ContractDocument | None:
        if document_id.value != DOC_ID:
            return None
        return ContractDocument.create(
            id=DocumentId(DOC_ID),
            filename="maersk.pdf",
            content_hash=ContentHash("a" * 64),
            size_bytes=len(PDF_BYTES),
        )

    async def find_by_content_hash(self, content_hash: ContentHash) -> ContractDocument | None:
        return None

    async def list_all(self, status: DocumentStatus | None = None) -> list[ContractDocument]:
        return []


class FakeStorage(IFileStorage):
    def __init__(self, present: bool = True) -> None:
        self.present = present

    async def save(self, doc_id: str, filename: str, content: bytes) -> str:
        return ""

    async def read(self, file_path: str) -> bytes:
        return PDF_BYTES

    async def exists(self, file_path: str) -> bool:
        return self.present


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_chunk_use_case] = lambda: GetChunkUseCase(FakeChunkRepo())
    app.dependency_overrides[get_document_file_use_case] = lambda: GetDocumentFileUseCase(
        FakeDocRepo(), FakeStorage()
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.unit
def test_chunk_endpoint_returns_original_fragment_with_location(client: TestClient) -> None:
    response = client.get(f"/api/v1/documents/{DOC_ID}/chunks/{CHUNK_ID}")

    assert response.status_code == 200
    assert response.json() == {
        "chunk_id": CHUNK_ID,
        "document_id": DOC_ID,
        "chunk_index": 3,
        "page_number": 2,
        "start_char": 10,
        "end_char": 62,
        "text": "Cláusula 4. Días libres: 7 días libres en terminal.",
    }


@pytest.mark.unit
def test_chunk_endpoint_404_for_unknown_chunk_or_document(client: TestClient) -> None:
    unknown_doc = "33333333-3333-4333-8333-333333333333"
    assert client.get(f"/api/v1/documents/{DOC_ID}/chunks/nope").status_code == 404
    assert client.get(f"/api/v1/documents/{unknown_doc}/chunks/{CHUNK_ID}").status_code == 404


@pytest.mark.unit
def test_chunk_endpoint_400_for_malformed_document_id(client: TestClient) -> None:
    assert client.get(f"/api/v1/documents/other/chunks/{CHUNK_ID}").status_code == 400


@pytest.mark.unit
def test_file_endpoint_serves_original_pdf_inline(client: TestClient) -> None:
    response = client.get(f"/api/v1/documents/{DOC_ID}/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'inline; filename="maersk.pdf"'
    assert response.content == PDF_BYTES


@pytest.mark.unit
def test_file_endpoint_404_when_document_or_file_is_missing(client: TestClient) -> None:
    assert (
        client.get("/api/v1/documents/33333333-3333-4333-8333-333333333333/file").status_code == 404
    )

    app.dependency_overrides[get_document_file_use_case] = lambda: GetDocumentFileUseCase(
        FakeDocRepo(), FakeStorage(present=False)
    )
    assert client.get(f"/api/v1/documents/{DOC_ID}/file").status_code == 404
