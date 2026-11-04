from pydantic import BaseModel, ConfigDict


class ContractDocumentResponse(BaseModel):
    """API response schema for a contract document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    filename: str
    status: str
    chunk_count: int
    size_bytes: int
    error_detail: str | None = None
    created_at: str | None = None


class ContractDocumentListResponse(BaseModel):
    """API response schema for a list of contract documents."""

    model_config = ConfigDict(extra="forbid")

    items: list[ContractDocumentResponse]
    total: int


class BatchUploadItemResponse(BaseModel):
    """Outcome of one file within a batch upload."""

    model_config = ConfigDict(extra="forbid")

    filename: str
    document: ContractDocumentResponse | None = None
    error: str | None = None


class BatchUploadResponse(BaseModel):
    """API response for a batch upload: one item per submitted file, in order."""

    model_config = ConfigDict(extra="forbid")

    items: list[BatchUploadItemResponse]
    accepted: int
    rejected: int
