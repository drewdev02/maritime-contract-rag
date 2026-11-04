from maritime.core.domain.events import DomainEvent


class Entity[ID]:
    """Base class for all domain entities, identifiable by an ID."""

    def __init__(self, id: ID) -> None:
        self._id = id

    @property
    def id(self) -> ID:
        return self._id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash((self.__class__, self.id))


class AggregateRoot[ID](Entity[ID]):
    """Aggregate root that encapsulates consistency boundaries and emits domain events."""

    def __init__(self, id: ID) -> None:
        super().__init__(id=id)
        self._domain_events: list[DomainEvent] = []

    def record_event(self, event: DomainEvent) -> None:
        """Records a domain event to be dispatched when changes are persisted."""
        self._domain_events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """Returns all recorded domain events and clears the internal buffer."""
        events = list(self._domain_events)
        self._domain_events.clear()
        return events

    def clear_events(self) -> None:
        """Clears all recorded domain events without returning them."""
        self._domain_events.clear()
