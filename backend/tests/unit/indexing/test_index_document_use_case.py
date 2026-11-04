from collections.abc import Sequence

import pytest

from maritime.core.events.in_memory import InMemoryEventBus
from maritime.core.exceptions import (
    CorruptedPdfError,
    PasswordProtectedPdfError,
)
from maritime.modules.indexing.application.use_cases import IndexDocumentUseCase
from maritime.modules.indexing.domain.entities import DocumentChunk
from maritime.modules.indexing.domain.ports import (
    IChunkingService,
    IChunkRepository,
    IEmbeddingService,
    IPdfParser,
    ParsedPage,
)
from maritime.modules.indexing.domain.value_objects import ChunkId, PageNumber, TextSpan
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.ports import IDocumentRepository, IFileStorage
from maritime.modules.ingestion.domain.value_objects import ContentHash, DocumentId, DocumentStatus


class InMemoryChunkRepository(IChunkRepository):
    def __init__(self) -> None:
        self.chunks: dict[str, list[DocumentChunk]] = {}

    async def save_chunks(self, chunks: Sequence[DocumentChunk]) -> None:
        for c in chunks:
            self.chunks.setdefault(c.document_id.value, []).append(c)

    async def delete_by_document_id(self, document_id: DocumentId) -> None:
        self.chunks.pop(document_id.value, None)

    async def find_by_document_id(self, document_id: DocumentId) -> list[DocumentChunk]:
        return self.chunks.get(document_id.value, [])

    async def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        document_id: DocumentId | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        return []


class InMemoryDocumentRepo(IDocumentRepository):
    def __init__(self) -> None:
        self.docs: dict[str, ContractDocument] = {}

    async def save(self, document: ContractDocument) -> None:
        self.docs[document.id.value] = document

    async def find_by_id(self, document_id: DocumentId) -> ContractDocument | None:
        return self.docs.get(document_id.value)

    async def find_by_content_hash(self, content_hash: ContentHash) -> ContractDocument | None:
        return next((d for d in self.docs.values() if d.content_hash == content_hash), None)

    async def list_all(self, status: DocumentStatus | None = None) -> list[ContractDocument]:
        return list(self.docs.values())


class InMemoryStorage(IFileStorage):
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def save(self, doc_id: str, filename: str, content: bytes) -> str:
        path = f"{doc_id}/{filename}"
        self.files[path] = content
        return path

    async def read(self, file_path: str) -> bytes:
        for path, data in self.files.items():
            if path in file_path or file_path in path:
                return data
        raise FileNotFoundError(f"File not found: {file_path}")

    async def exists(self, file_path: str) -> bool:
        return any(path in file_path or file_path in path for path in self.files)


class DummyParser(IPdfParser):
    def __init__(self, should_fail_corrupt: bool = False, should_fail_pw: bool = False) -> None:
        self.should_fail_corrupt = should_fail_corrupt
        self.should_fail_pw = should_fail_pw

    def parse(self, pdf_bytes: bytes) -> list[ParsedPage]:
        if self.should_fail_pw:
            raise PasswordProtectedPdfError("El documento está protegido por contraseña")
        if self.should_fail_corrupt:
            raise CorruptedPdfError("Archivo corrupto o sin páginas legibles")
        return [
            ParsedPage(
                page_number=1,
                text="Contrato de Fletamento.",
                tables=["| Col1 | Col2 |\n| --- | --- |\n| A | B |"],
            )
        ]


class DummyChunker(IChunkingService):
    def chunk(self, pages: list[ParsedPage], document_id: DocumentId) -> list[DocumentChunk]:
        return [
            DocumentChunk(
                id=ChunkId.generate(),
                document_id=document_id,
                chunk_index=0,
                page_number=PageNumber(1),
                text="Contrato de Fletamento.",
                span=TextSpan(0, 23),
            )
        ]


class DummyEmbedding(IEmbeddingService):
    def embed_text(self, text: str) -> list[float]:
        return [0.1] * 768

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.1] * 768 for _ in texts]


class EmptyChunker(IChunkingService):
    def chunk(self, pages: list[ParsedPage], document_id: DocumentId) -> list[DocumentChunk]:
        return []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_index_document_empty_chunks_fails_with_specific_error() -> None:
    doc_repo = InMemoryDocumentRepo()
    chunk_repo = InMemoryChunkRepository()
    storage = InMemoryStorage()
    parser = DummyParser()
    chunker = EmptyChunker()
    embedding = DummyEmbedding()
    event_bus = InMemoryEventBus()

    doc_id = DocumentId.generate()
    doc = ContractDocument.create(
        id=doc_id,
        filename="empty.pdf",
        content_hash=ContentHash("d" * 64),
        size_bytes=50,
    )
    await doc_repo.save(doc)
    await storage.save(doc_id.value, doc.filename, b"empty content")

    use_case = IndexDocumentUseCase(
        document_repository=doc_repo,
        chunk_repository=chunk_repo,
        file_storage=storage,
        pdf_parser=parser,
        chunking_service=chunker,
        embedding_service=embedding,
        event_bus=event_bus,
    )

    await use_case.execute(doc_id.value)

    saved_doc = await doc_repo.find_by_id(doc_id)
    assert saved_doc is not None
    assert saved_doc.status == DocumentStatus.FAILED
    assert saved_doc.error_detail == "No se pudieron extraer fragmentos válidos del documento."
    assert len(await chunk_repo.find_by_document_id(doc_id)) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_index_document_success() -> None:
    doc_repo = InMemoryDocumentRepo()
    chunk_repo = InMemoryChunkRepository()
    storage = InMemoryStorage()
    parser = DummyParser()
    chunker = DummyChunker()
    embedding = DummyEmbedding()
    event_bus = InMemoryEventBus()

    doc_id = DocumentId.generate()
    doc = ContractDocument.create(
        id=doc_id,
        filename="test.pdf",
        content_hash=ContentHash("a" * 64),
        size_bytes=100,
    )
    await doc_repo.save(doc)
    await storage.save(doc_id.value, doc.filename, b"%PDF-1.4 dummy")

    use_case = IndexDocumentUseCase(
        document_repository=doc_repo,
        chunk_repository=chunk_repo,
        file_storage=storage,
        pdf_parser=parser,
        chunking_service=chunker,
        embedding_service=embedding,
        event_bus=event_bus,
    )

    await use_case.execute(doc_id.value)

    # Document must be READY
    saved_doc = await doc_repo.find_by_id(doc_id)
    assert saved_doc is not None
    assert saved_doc.status == DocumentStatus.READY
    assert saved_doc.chunk_count == 1
    assert saved_doc.error_detail is None

    # Chunks must be saved
    saved_chunks = await chunk_repo.find_by_document_id(doc_id)
    assert len(saved_chunks) == 1
    assert saved_chunks[0].embedding == [0.1] * 768


@pytest.mark.unit
@pytest.mark.asyncio
async def test_index_document_password_protected_fails_gracefully() -> None:
    doc_repo = InMemoryDocumentRepo()
    chunk_repo = InMemoryChunkRepository()
    storage = InMemoryStorage()
    parser = DummyParser(should_fail_pw=True)
    chunker = DummyChunker()
    embedding = DummyEmbedding()
    event_bus = InMemoryEventBus()

    doc_id = DocumentId.generate()
    doc = ContractDocument.create(
        id=doc_id,
        filename="protected.pdf",
        content_hash=ContentHash("b" * 64),
        size_bytes=100,
    )
    await doc_repo.save(doc)
    await storage.save(doc_id.value, doc.filename, b"encrypted bytes")

    use_case = IndexDocumentUseCase(
        document_repository=doc_repo,
        chunk_repository=chunk_repo,
        file_storage=storage,
        pdf_parser=parser,
        chunking_service=chunker,
        embedding_service=embedding,
        event_bus=event_bus,
    )

    await use_case.execute(doc_id.value)

    saved_doc = await doc_repo.find_by_id(doc_id)
    assert saved_doc is not None
    assert saved_doc.status == DocumentStatus.FAILED
    assert saved_doc.error_detail == "El documento está protegido por contraseña"
    assert len(await chunk_repo.find_by_document_id(doc_id)) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_index_document_corrupted_fails_gracefully() -> None:
    doc_repo = InMemoryDocumentRepo()
    chunk_repo = InMemoryChunkRepository()
    storage = InMemoryStorage()
    parser = DummyParser(should_fail_corrupt=True)
    chunker = DummyChunker()
    embedding = DummyEmbedding()
    event_bus = InMemoryEventBus()

    doc_id = DocumentId.generate()
    doc = ContractDocument.create(
        id=doc_id,
        filename="corrupted.pdf",
        content_hash=ContentHash("c" * 64),
        size_bytes=100,
    )
    await doc_repo.save(doc)
    await storage.save(doc_id.value, doc.filename, b"corrupted bytes")

    use_case = IndexDocumentUseCase(
        document_repository=doc_repo,
        chunk_repository=chunk_repo,
        file_storage=storage,
        pdf_parser=parser,
        chunking_service=chunker,
        embedding_service=embedding,
        event_bus=event_bus,
    )

    await use_case.execute(doc_id.value)

    saved_doc = await doc_repo.find_by_id(doc_id)
    assert saved_doc is not None
    assert saved_doc.status == DocumentStatus.FAILED
    assert saved_doc.error_detail == "Archivo corrupto o sin páginas legibles"
    assert len(await chunk_repo.find_by_document_id(doc_id)) == 0
