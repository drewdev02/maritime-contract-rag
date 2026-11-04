from collections import defaultdict
from collections.abc import Sequence
from typing import Any, TypeVar

from maritime.core.domain.events import DomainEvent
from maritime.core.events.event_bus import EventHandler, IEventBus

E = TypeVar("E", bound=DomainEvent)


class InMemoryEventBus(IEventBus):
    """In-memory event bus implementation for testing and local asynchronous dispatch."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler[Any]]] = defaultdict(list)
        self._published_events: list[DomainEvent] = []

    def subscribe(self, event_type: type[E], handler: EventHandler[E]) -> None:
        """Subscribes an async handler to a domain event type."""
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Publishes an event to all subscribed handlers and records it in history."""
        self._published_events.append(event)
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            await handler(event)

    async def publish_all(self, events: Sequence[DomainEvent]) -> None:
        """Publishes all events sequentially."""
        for event in events:
            await self.publish(event)

    @property
    def published_events(self) -> list[DomainEvent]:
        """Returns a copy of all published events for inspection/assertions."""
        return list(self._published_events)

    def clear_history(self) -> None:
        """Clears the history of published events."""
        self._published_events.clear()
