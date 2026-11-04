import uuid
from dataclasses import dataclass

from maritime.core.domain.value_object import ValueObject
from maritime.core.exceptions import InvariantViolationError


@dataclass(frozen=True, slots=True)
class ChunkId(ValueObject):
    """Value object representing the unique identifier of a document chunk."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str):
            raise InvariantViolationError("ChunkId cannot be empty.")

    @classmethod
    def generate(cls) -> "ChunkId":
        return cls(str(uuid.uuid4()))

    @classmethod
    def from_str(cls, value: str) -> "ChunkId":
        try:
            val = str(uuid.UUID(value))
            return cls(val)
        except (ValueError, TypeError) as e:
            raise InvariantViolationError(f"Invalid UUID string for ChunkId: '{value}'") from e


@dataclass(frozen=True, slots=True)
class PageNumber(ValueObject):
    """Value object representing a 1-indexed document page number."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or self.value < 1:
            raise InvariantViolationError(
                f"Page number must be a positive integer >= 1, got {self.value}."
            )


@dataclass(frozen=True, slots=True)
class TextSpan(ValueObject):
    """Value object representing character boundaries of a chunk within a document page."""

    start_char: int
    end_char: int

    def __post_init__(self) -> None:
        if self.start_char < 0:
            raise InvariantViolationError(f"start_char cannot be negative, got {self.start_char}.")
        if self.end_char < self.start_char:
            raise InvariantViolationError(
                f"end_char ({self.end_char}) cannot be less than start_char ({self.start_char})."
            )

    @property
    def length(self) -> int:
        return self.end_char - self.start_char
