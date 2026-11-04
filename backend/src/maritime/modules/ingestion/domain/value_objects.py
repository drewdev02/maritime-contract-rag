from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4

from maritime.core.domain.value_object import ValueObject
from maritime.core.exceptions import InvariantViolationError


class DocumentStatus(StrEnum):
    """Lifecycle states of a contract document."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DocumentId(ValueObject):
    """Unique identifier for a contract document."""

    value: str

    def __post_init__(self) -> None:
        try:
            UUID(self.value)
        except (ValueError, AttributeError, TypeError) as err:
            raise InvariantViolationError(
                f"Invalid DocumentId: '{self.value}'. Must be a valid UUID."
            ) from err

    @classmethod
    def generate(cls) -> "DocumentId":
        return cls(value=str(uuid4()))

    @classmethod
    def from_str(cls, value: str) -> "DocumentId":
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ContentHash(ValueObject):
    """SHA-256 hash identifying the immutable content of a document."""

    value: str

    def __str__(self) -> str:
        return self.value

    def __post_init__(self) -> None:
        if len(self.value) != 64:
            raise InvariantViolationError(
                f"Invalid ContentHash length: {len(self.value)}. Must be a 64-character hex string."
            )
        try:
            int(self.value, 16)
        except ValueError as err:
            raise InvariantViolationError(
                f"Invalid ContentHash hexadecimal format: '{self.value}'."
            ) from err
