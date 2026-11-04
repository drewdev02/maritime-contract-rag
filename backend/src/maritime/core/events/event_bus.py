from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine, Sequence
from typing import Any, TypeVar

from maritime.core.domain.events import DomainEvent

E = TypeVar("E", bound=DomainEvent)
EventHandler = Callable[[E], Coroutine[Any, Any, None]]


class IEventBus(ABC):
    """Port for publishing and subscribing to domain and integration events."""

    @abstractmethod
    def subscribe(self, event_type: type[E], handler: EventHandler[E]) -> None:
        """Subscribes an asynchronous handler to a specific domain event type."""
        pass

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publishes a single domain event to all subscribed handlers."""
        pass

    @abstractmethod
    async def publish_all(self, events: Sequence[DomainEvent]) -> None:
        """Publishes multiple domain events in sequential order."""
        pass
