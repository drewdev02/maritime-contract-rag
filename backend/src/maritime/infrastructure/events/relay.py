from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

from opentelemetry import propagate

from maritime.core.domain.events import DomainEvent
from maritime.core.events.event_bus import E, EventHandler, IEventBus
from maritime.core.events.registry import EventRegistry
from maritime.core.events.stream import IEventStream
from maritime.core.exceptions import EventDecodeError
from maritime.core.telemetry.logging import get_logger
from maritime.core.telemetry.tracer import span

logger = get_logger(__name__)


class RelayEventBus(IEventBus):
    """Delivers every event to this process's own subscribers and appends it to the shared stream.

    Local subscribers run synchronously and may raise (for example, queuing the indexing task
    failed), because the caller needs to know. Other processes read the stream; a failure to reach
    it is logged and swallowed: events are notifications, and the state they describe is already
    committed in the database. That makes stream delivery at-most-once from the publisher.

    The stream is opened through a factory for every publish. The worker runs each task in a fresh
    event loop, and an async Redis connection cannot be reused across loops.
    """

    def __init__(
        self,
        registry: EventRegistry,
        stream_factory: Callable[[], IEventStream] | None = None,
    ) -> None:
        self._registry = registry
        self._stream_factory = stream_factory
        self._handlers: dict[type[DomainEvent], list[EventHandler[Any]]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: EventHandler[E]) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        await self.publish_all([event])

    async def publish_all(self, events: Sequence[DomainEvent]) -> None:
        for event in events:
            for handler in self._handlers.get(type(event), []):
                await handler(event)
        await self._append_to_stream(events)

    async def _append_to_stream(self, events: Sequence[DomainEvent]) -> None:
        if self._stream_factory is None or not events:
            return
        stream = self._stream_factory()
        try:
            with span("event.publish", **{"event.count": len(events)}):
                carrier: dict[str, str] = {}
                propagate.inject(carrier)
                for event in events:
                    envelope = self._registry.encode(event, carrier.get("traceparent"))
                    await stream.append(envelope)
        except EventDecodeError:
            logger.error("Event type is not registered; it was not published", exc_info=True)
        except Exception:
            logger.warning("Could not publish events to the stream", exc_info=True)
        finally:
            await stream.close()
