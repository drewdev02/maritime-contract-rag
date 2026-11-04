from dataclasses import dataclass

from maritime.core.domain.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class Citation(ValueObject):
    """Represents a direct, verifiable textual citation within a contract document."""

    chunk_id: str
    document_id: str
    document_name: str
    page_number: int
    snippet_text: str


@dataclass(frozen=True, slots=True)
class RetrievedChunk(ValueObject):
    """Represents a chunk retrieved via dense vector similarity from pgvector."""

    chunk_id: str
    document_id: str
    document_name: str
    page_number: int
    text: str
    similarity_score: float


@dataclass(frozen=True, slots=True)
class RagResponse(ValueObject):
    """Structured response from the contract RAG assistant."""

    answer: str
    citations: list[Citation]
    has_sufficient_evidence: bool
    confidence_score: float | None = None


@dataclass(frozen=True, slots=True)
class StreamDeltaChunk(ValueObject):
    """Incremental text token/chunk generated during answer streaming."""

    delta: str


@dataclass(frozen=True, slots=True)
class StreamMetaChunk(ValueObject):
    """Metadata emitted during or at the end of streaming containing citations and evidence info."""

    citations: list[Citation]
    has_sufficient_evidence: bool
    confidence_score: float | None = None


StreamChunk = StreamDeltaChunk | StreamMetaChunk
