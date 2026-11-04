from maritime.core.domain.entity import Entity
from maritime.core.exceptions import InvariantViolationError
from maritime.modules.indexing.domain.value_objects import ChunkId, PageNumber, TextSpan
from maritime.modules.ingestion.domain.value_objects import DocumentId


class DocumentChunk(Entity[ChunkId]):
    """Entity representing an indexed textual/tabular fragment of a contract document."""

    EXPECTED_EMBEDDING_DIM = 768

    def __init__(
        self,
        id: ChunkId,
        document_id: DocumentId,
        chunk_index: int,
        page_number: PageNumber,
        text: str,
        span: TextSpan,
        embedding: list[float] | None = None,
    ) -> None:
        super().__init__(id=id)
        if chunk_index < 0:
            raise InvariantViolationError(f"chunk_index cannot be negative, got {chunk_index}.")
        if not text or not text.strip():
            raise InvariantViolationError("Chunk text cannot be empty or whitespace.")

        self.document_id = document_id
        self.chunk_index = chunk_index
        self.page_number = page_number
        self.text = text
        self.span = span
        self.embedding = embedding

        if embedding is not None:
            self._validate_embedding(embedding)

    def attach_embedding(self, embedding: list[float]) -> None:
        """Attaches a computed vector embedding to this chunk after dimension validation."""
        self._validate_embedding(embedding)
        self.embedding = list(embedding)

    def _validate_embedding(self, embedding: list[float]) -> None:
        if len(embedding) != self.EXPECTED_EMBEDDING_DIM:
            raise InvariantViolationError(
                f"Expected embedding dimension of {self.EXPECTED_EMBEDDING_DIM}, got {len(embedding)}."
            )
        if not all(isinstance(x, (int, float)) for x in embedding):
            raise InvariantViolationError("Embedding vector elements must be numeric floats.")
