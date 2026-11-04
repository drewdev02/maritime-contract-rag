from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    """Payload for submitting a natural language query against contract documents."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description="Natural language question regarding contract terms, rates, or clauses",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of candidate chunks to retrieve",
    )
    document_id: str | None = Field(
        default=None,
        description="Optional document ID to scope retrieval to a specific contract",
    )


class CitationResponse(BaseModel):
    """Verifiable textual citation accompanying an assistant response."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(description="Unique identifier of the source chunk")
    document_id: str = Field(description="Unique identifier of the contract document")
    document_name: str = Field(description="Filename of the contract document")
    page_number: int = Field(description="1-based page number where the statement appears")
    snippet_text: str = Field(description="Verbatim excerpt from the contract document")


class QueryResponse(BaseModel):
    """Structured response from the contract RAG assistant."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(description="Synthesized answer in clear, impersonal tone")
    citations: list[CitationResponse] = Field(
        default_factory=list,
        description="List of verifiable citations backing the answer",
    )
    has_sufficient_evidence: bool = Field(
        description="Indicates whether the response is fully supported by documentary evidence"
    )
    confidence_score: float | None = Field(
        default=None,
        description="Optional similarity or confidence metric (0.0 to 1.0)",
    )
