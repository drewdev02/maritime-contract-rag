import pytest

from maritime.core.exceptions import InvariantViolationError
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)


@pytest.mark.unit
def test_document_status_enum_values_in_english() -> None:
    assert DocumentStatus.PENDING.value == "pending"
    assert DocumentStatus.PROCESSING.value == "processing"
    assert DocumentStatus.READY.value == "ready"
    assert DocumentStatus.FAILED.value == "failed"


@pytest.mark.unit
def test_document_id_generation_and_validation() -> None:
    doc_id = DocumentId.generate()
    assert len(doc_id.value) == 36
    assert DocumentId.from_str(doc_id.value) == doc_id


@pytest.mark.unit
def test_document_id_invalid_raises_error() -> None:
    with pytest.raises(InvariantViolationError, match="Invalid DocumentId"):
        DocumentId.from_str("invalid-uuid")


@pytest.mark.unit
def test_content_hash_validation() -> None:
    valid_sha256 = "a" * 64
    ch = ContentHash(valid_sha256)
    assert ch.value == valid_sha256


@pytest.mark.unit
def test_content_hash_invalid_length_or_characters_raises_error() -> None:
    with pytest.raises(InvariantViolationError, match="Invalid ContentHash"):
        ContentHash("short_hash")

    with pytest.raises(InvariantViolationError, match="Invalid ContentHash"):
        ContentHash("z" * 64)  # non-hex
