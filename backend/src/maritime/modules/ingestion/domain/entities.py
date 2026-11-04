from datetime import UTC, datetime

from maritime.core.domain.entity import AggregateRoot
from maritime.core.exceptions import InvalidStateTransitionError, InvariantViolationError
from maritime.modules.ingestion.domain.events import (
    DocumentFailedEvent,
    DocumentProcessingStartedEvent,
    DocumentReadyEvent,
    DocumentUploadedEvent,
)
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)


class ContractDocument(AggregateRoot[DocumentId]):
    """Aggregate Root representing a maritime contract document throughout its lifecycle."""

    def __init__(
        self,
        id: DocumentId,
        filename: str,
        content_hash: ContentHash,
        size_bytes: int,
        status: DocumentStatus = DocumentStatus.PENDING,
        chunk_count: int = 0,
        error_detail: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        super().__init__(id=id)
        self.filename = filename
        self.content_hash = content_hash
        self.size_bytes = size_bytes
        self.status = status
        self.chunk_count = chunk_count
        self.error_detail = error_detail
        self.created_at = created_at or datetime.now(UTC)

    @classmethod
    def create(
        cls,
        id: DocumentId,
        filename: str,
        content_hash: ContentHash,
        size_bytes: int,
    ) -> "ContractDocument":
        """Factory method to create a new contract document aggregate in PENDING status."""
        doc = cls(
            id=id,
            filename=filename,
            content_hash=content_hash,
            size_bytes=size_bytes,
            status=DocumentStatus.PENDING,
            chunk_count=0,
            error_detail=None,
            created_at=datetime.now(UTC),
        )
        doc.record_event(
            DocumentUploadedEvent(
                document_id=id.value,
                content_hash=content_hash.value,
                filename=filename,
            )
        )
        return doc

    def mark_as_processing(self) -> None:
        """Transitions document status to PROCESSING."""
        if self.status == DocumentStatus.READY:
            raise InvalidStateTransitionError(
                entity_name="ContractDocument",
                current_state=self.status.value,
                target_state=DocumentStatus.PROCESSING.value,
            )
        self.status = DocumentStatus.PROCESSING
        self.record_event(DocumentProcessingStartedEvent(document_id=self.id.value))

    def mark_as_ready(self, total_chunks: int) -> None:
        """Transitions document status to READY and sets indexed chunk count."""
        if total_chunks <= 0:
            raise InvariantViolationError(
                f"A ready document must have at least one chunk indexed, got {total_chunks}."
            )
        self.status = DocumentStatus.READY
        self.chunk_count = total_chunks
        self.error_detail = None
        self.record_event(
            DocumentReadyEvent(
                document_id=self.id.value,
                chunk_count=total_chunks,
            )
        )

    def request_retry(self) -> None:
        """Moves a FAILED document back to PENDING and asks for it to be processed again."""
        if self.status != DocumentStatus.FAILED:
            raise InvalidStateTransitionError(
                entity_name="ContractDocument",
                current_state=self.status.value,
                target_state=DocumentStatus.PENDING.value,
            )
        self.status = DocumentStatus.PENDING
        self.error_detail = None
        self.record_event(
            DocumentUploadedEvent(
                document_id=self.id.value,
                content_hash=self.content_hash.value,
                filename=self.filename,
            )
        )

    def mark_as_failed(self, reason: str) -> None:
        """Transitions document status to FAILED and records the failure reason."""
        self.status = DocumentStatus.FAILED
        self.error_detail = reason
        self.record_event(
            DocumentFailedEvent(
                document_id=self.id.value,
                reason=reason,
            )
        )
