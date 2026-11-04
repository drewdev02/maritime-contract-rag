from abc import ABC, abstractmethod

from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)


class IDocumentRepository(ABC):
    """Port for persisting and retrieving ContractDocument aggregates."""

    @abstractmethod
    async def save(self, document: ContractDocument) -> None:
        """Persists or updates a contract document aggregate."""
        pass

    @abstractmethod
    async def find_by_id(self, document_id: DocumentId) -> ContractDocument | None:
        """Retrieves a document by its unique identity."""
        pass

    @abstractmethod
    async def find_by_content_hash(self, content_hash: ContentHash) -> ContractDocument | None:
        """Retrieves an existing document by its immutable SHA-256 content hash."""
        pass

    @abstractmethod
    async def list_all(self, status: DocumentStatus | None = None) -> list[ContractDocument]:
        """Lists contract documents, optionally filtered by status."""
        pass


class IFileStorage(ABC):
    """Port for physical file storage operations."""

    @abstractmethod
    async def save(self, doc_id: str, filename: str, content: bytes) -> str:
        """Stores file content and returns its permanent storage URI or path."""
        pass

    @abstractmethod
    async def read(self, file_path: str) -> bytes:
        """Reads file binary content from storage."""
        pass

    @abstractmethod
    async def exists(self, file_path: str) -> bool:
        """Checks if a file exists in storage."""
        pass
