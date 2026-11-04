class ValueObject:
    """Marker base class for domain Value Objects.

    Value Objects are immutable and defined purely by their attributes rather than an identity.
    Derived classes should use `@dataclass(frozen=True, slots=True)`.
    """

    pass
