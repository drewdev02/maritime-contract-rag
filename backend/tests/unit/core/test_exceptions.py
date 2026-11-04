import pytest

from maritime.core.exceptions import (
    ConflictError,
    DomainError,
    EntityNotFoundError,
    InsufficientEvidenceError,
    InvalidStateTransitionError,
    InvariantViolationError,
    UnverifiedCitationError,
)


@pytest.mark.unit
def test_domain_exception_hierarchy() -> None:
    assert issubclass(EntityNotFoundError, DomainError)
    assert issubclass(InvariantViolationError, DomainError)
    assert issubclass(InvalidStateTransitionError, InvariantViolationError)
    assert issubclass(ConflictError, DomainError)
    assert issubclass(UnverifiedCitationError, DomainError)
    assert issubclass(InsufficientEvidenceError, DomainError)


@pytest.mark.unit
def test_entity_not_found_error_message() -> None:
    err = EntityNotFoundError(entity_name="ContractDocument", entity_id="doc-123")
    assert "ContractDocument" in str(err)
    assert "doc-123" in str(err)
    assert err.entity_name == "ContractDocument"
    assert err.entity_id == "doc-123"


@pytest.mark.unit
def test_invalid_state_transition_error() -> None:
    err = InvalidStateTransitionError(
        entity_name="ContractDocument",
        current_state="ready",
        target_state="processing",
    )
    assert "ContractDocument" in str(err)
    assert "ready" in str(err)
    assert "processing" in str(err)
