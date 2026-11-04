from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field

from maritime.modules.indexing.domain.entities import DocumentChunk
from maritime.modules.ingestion.domain.value_objects import DocumentId


@dataclass(frozen=True, slots=True)
class ParsedPage:
    """Represents the raw parsed contents of a single PDF page."""

    page_number: int
    text: str
    tables: list[str] = field(default_factory=list)


class IPdfParser(ABC):
    """Port for PDF extraction preserving structural tables and text."""

    @abstractmethod
    def parse(self, pdf_bytes: bytes) -> list[ParsedPage]:
        """Parses a PDF binary into pages with text and markdown tables.

        Raises:
            CorruptedPdfError: If the binary is empty or malformed.
            PasswordProtectedPdfError: If the PDF is password-encrypted.
        """
        pass


class IChunkingService(ABC):
    """Port for segmenting parsed pages into indexed document chunks."""

    @abstractmethod
    def chunk(self, pages: list[ParsedPage], document_id: DocumentId) -> list[DocumentChunk]:
        """Segments parsed pages into DocumentChunk entities preserving offsets."""
        pass


class IEmbeddingService(ABC):
    """Port for generating dense vector embeddings from text."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generates a 768-dimensional embedding vector for a single text."""
        pass

    @abstractmethod
    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Generates embeddings for a batch of texts."""
        pass


class IChunkRepository(ABC):
    """Port for persisting and querying document chunks with pgvector."""

    @abstractmethod
    async def save_chunks(self, chunks: Sequence[DocumentChunk]) -> None:
        """Persists a sequence of chunks and their vector embeddings."""
        pass

    @abstractmethod
    async def delete_by_document_id(self, document_id: DocumentId) -> None:
        """Deletes all chunks associated with a document (for idempotent retries)."""
        pass

    @abstractmethod
    async def find_by_document_id(self, document_id: DocumentId) -> list[DocumentChunk]:
        """Retrieves all chunks for a document ordered by chunk_index."""
        pass

    @abstractmethod
    async def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        document_id: DocumentId | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Performs cosine similarity search returning chunks and similarity scores (0.0 - 1.0)."""
        pass
