import pytest

from maritime.core.exceptions import InvariantViolationError
from maritime.modules.indexing.domain.entities import DocumentChunk
from maritime.modules.indexing.domain.value_objects import ChunkId, PageNumber, TextSpan
from maritime.modules.ingestion.domain.value_objects import DocumentId


@pytest.mark.unit
def test_chunk_id_validation() -> None:
    chunk_id = ChunkId.generate()
    assert len(chunk_id.value) == 36

    with pytest.raises(InvariantViolationError):
        ChunkId("")

    with pytest.raises(InvariantViolationError):
        ChunkId.from_str("not-a-valid-uuid")


@pytest.mark.unit
def test_page_number_validation() -> None:
    page = PageNumber(1)
    assert page.value == 1

    with pytest.raises(InvariantViolationError):
        PageNumber(0)

    with pytest.raises(InvariantViolationError):
        PageNumber(-5)


@pytest.mark.unit
def test_text_span_validation() -> None:
    span = TextSpan(start_char=10, end_char=50)
    assert span.length == 40

    with pytest.raises(InvariantViolationError):
        TextSpan(start_char=-1, end_char=10)

    with pytest.raises(InvariantViolationError):
        TextSpan(start_char=20, end_char=10)


@pytest.mark.unit
def test_document_id_rejects_non_uuid_values() -> None:
    with pytest.raises(InvariantViolationError):
        DocumentId("doc-123")

    with pytest.raises(InvariantViolationError):
        DocumentId("")


@pytest.mark.unit
def test_document_chunk_entity_invariants() -> None:
    chunk_id = ChunkId.generate()
    span = TextSpan(start_char=0, end_char=25)
    page = PageNumber(1)

    document_id = DocumentId.generate()

    chunk = DocumentChunk(
        id=chunk_id,
        document_id=document_id,
        chunk_index=0,
        page_number=page,
        text="Cláusula 1: Flete marítimo",
        span=span,
    )

    assert chunk.id == chunk_id
    assert chunk.text == "Cláusula 1: Flete marítimo"
    assert chunk.embedding is None

    # Empty text invariant
    with pytest.raises(InvariantViolationError, match="Chunk text cannot be empty"):
        DocumentChunk(
            id=chunk_id,
            document_id=document_id,
            chunk_index=0,
            page_number=page,
            text="   ",
            span=span,
        )

    # Invalid embedding dimension
    with pytest.raises(InvariantViolationError, match="Expected embedding dimension of 768"):
        chunk.attach_embedding([0.1, 0.2])

    # Valid embedding
    valid_embedding = [0.0] * 768
    chunk.attach_embedding(valid_embedding)
    assert chunk.embedding == valid_embedding
