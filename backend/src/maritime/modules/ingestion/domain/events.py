from dataclasses import dataclass

from maritime.core.domain.events import DomainEvent
from maritime.core.events.registry import EventRegistry


@dataclass(frozen=True, slots=True)
class DocumentUploadedEvent(DomainEvent):
    """Emitted when a new contract document is uploaded and persisted."""

    document_id: str
    content_hash: str
    filename: str


@dataclass(frozen=True, slots=True)
class DocumentProcessingStartedEvent(DomainEvent):
    """Emitted when the indexing pipeline begins processing a document."""

    document_id: str


@dataclass(frozen=True, slots=True)
class DocumentReadyEvent(DomainEvent):
    """Emitted when a document has been completely indexed and ready for queries."""

    document_id: str
    chunk_count: int


@dataclass(frozen=True, slots=True)
class DocumentFailedEvent(DomainEvent):
    """Emitted when document indexing fails."""

    document_id: str
    reason: str


def register_ingestion_events(registry: EventRegistry) -> None:
    """Gives each ingestion event a stable wire name. Never rename these once released."""
    registry.register("document.uploaded", DocumentUploadedEvent)
    registry.register("document.processing_started", DocumentProcessingStartedEvent)
    registry.register("document.ready", DocumentReadyEvent)
    registry.register("document.failed", DocumentFailedEvent)
