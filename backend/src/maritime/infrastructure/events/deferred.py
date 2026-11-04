from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from contextvars import ContextVar

from maritime.core.domain.events import DomainEvent
from maritime.core.events.event_bus import E, EventHandler, IEventBus


class EventScope:
    """Events published while a scope is active, waiting for the transaction to commit."""

    def __init__(self, bus: IEventBus) -> None:
        self._bus = bus
        self._pending: list[DomainEvent] = []

    def add(self, events: Sequence[DomainEvent]) -> None:
        self._pending.extend(events)

    async def flush(self) -> None:
        """Publishes what was buffered. Call it only after the transaction committed."""
        events, self._pending = self._pending, []
        if events:
            await self._bus.publish_all(events)

    def discard(self) -> None:
        self._pending.clear()


class _NoScope(EventScope):
    """Scope for buses that publish immediately: nothing is ever buffered."""

    def __init__(self) -> None:
        super().__init__(bus=_NoBus())

    async def flush(self) -> None:
        return None


class _NoBus(IEventBus):
    def subscribe(self, event_type: type[E], handler: EventHandler[E]) -> None:
        return None

    async def publish(self, event: DomainEvent) -> None:
        return None

    async def publish_all(self, events: Sequence[DomainEvent]) -> None:
        return None


class DeferredEventBus(IEventBus):
    """Holds events until the surrounding transaction has committed.

    Publishing inside a request or a task would announce facts the database does not show yet (a
    worker could be told about a document that is not visible) and would announce facts that a
    later rollback undoes. Inside ``scope()`` events are buffered; ``flush()`` after the commit
    publishes them and leaving the scope drops anything not flushed. Outside a scope the bus
    publishes immediately.
    """

    def __init__(self, inner: IEventBus) -> None:
        self._inner = inner
        self._scope: ContextVar[EventScope | None] = ContextVar("event_scope", default=None)

    def subscribe(self, event_type: type[E], handler: EventHandler[E]) -> None:
        self._inner.subscribe(event_type, handler)

    async def publish(self, event: DomainEvent) -> None:
        await self.publish_all([event])

    async def publish_all(self, events: Sequence[DomainEvent]) -> None:
        scope = self._scope.get()
        if scope is None:
            await self._inner.publish_all(events)
        else:
            scope.add(events)

    @asynccontextmanager
    async def scope(self) -> AsyncIterator[EventScope]:
        scope = EventScope(self._inner)
        token = self._scope.set(scope)
        try:
            yield scope
        finally:
            self._scope.reset(token)
            scope.discard()


def transaction_scope(bus: IEventBus) -> AbstractAsyncContextManager[EventScope]:
    """Opens an after-commit scope on a deferred bus, or a no-op scope on any other bus."""
    if isinstance(bus, DeferredEventBus):
        return bus.scope()
    return _noop_scope()


@asynccontextmanager
async def _noop_scope() -> AsyncIterator[EventScope]:
    yield _NoScope()
