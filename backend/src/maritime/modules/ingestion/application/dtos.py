from pydantic import BaseModel, ConfigDict


class DocumentStatusDto(BaseModel):
    """DTO representing the current processing status of a contract document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    status: str
    chunk_count: int
    size_bytes: int
    error_detail: str | None = None
    created_at: str | None = None


class UploadFileDto(BaseModel):
    """One file submitted for upload: its client-side name and raw bytes."""

    model_config = ConfigDict(extra="forbid")

    filename: str
    content: bytes


class BatchUploadItemDto(BaseModel):
    """Outcome of one file in a batch: the stored document, or why it was rejected."""

    model_config = ConfigDict(extra="forbid")

    filename: str
    document: DocumentStatusDto | None = None
    error: str | None = None


class BatchUploadResultDto(BaseModel):
    """Outcome of a batch upload: one item per submitted file, in submission order."""

    model_config = ConfigDict(extra="forbid")

    items: list[BatchUploadItemDto]
    accepted: int
    rejected: int


class DocumentSummaryDto(BaseModel):
    """DTO summarizing a contract document for listing views."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    status: str
    chunk_count: int
    size_bytes: int
    error_detail: str | None = None
    created_at: str | None = None
