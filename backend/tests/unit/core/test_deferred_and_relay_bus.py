import pytest

from maritime.core.domain.events import DomainEvent
from maritime.core.events.envelope import EventEnvelope
from maritime.core.events.event_bus import IEventBus
from maritime.core.events.in_memory import InMemoryEventBus
from maritime.core.events.stream import IEventStream, StreamEntry
from maritime.infrastructure.event_registry import build_event_registry
from maritime.infrastructure.events.deferred import DeferredEventBus, transaction_scope
from maritime.infrastructure.events.relay import RelayEventBus
from maritime.modules.ingestion.domain.events import DocumentReadyEvent, DocumentUploadedEvent


def _ready(n: int = 1) -> DocumentReadyEvent:
    return DocumentReadyEvent(document_id=f"d{n}", chunk_count=n)


class FakeStream(IEventStream):
    def __init__(self, fail: bool = False) -> None:
        self.envelopes: list[EventEnvelope] = []
        self.closed = 0
        self._fail = fail

    async def append(self, envelope: EventEnvelope) -> str:
        if self._fail:
            raise ConnectionError("redis is down")
        self.envelopes.append(envelope)
        return f"{len(self.envelopes)}-0"

    async def read(self, last_id: str, block_ms: int = 5000, count: int = 100) -> list[StreamEntry]:
        return []

    async def replay(self, after_id: str, count: int = 1000) -> list[StreamEntry]:
        return []

    async def tail_id(self) -> str:
        return "0-0"

    async def close(self) -> None:
        self.closed += 1


# --- DeferredEventBus -------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_events_inside_a_scope_wait_for_the_flush() -> None:
    inner = InMemoryEventBus()
    bus = DeferredEventBus(inner)

    async with bus.scope() as scope:
        await bus.publish_all([_ready(1), _ready(2)])
        assert inner.published_events == []

        await scope.flush()

        assert [
            e.document_id for e in inner.published_events if isinstance(e, DocumentReadyEvent)
        ] == [
            "d1",
            "d2",
        ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_events_not_flushed_because_the_transaction_failed_are_dropped() -> None:
    inner = InMemoryEventBus()
    bus = DeferredEventBus(inner)

    with pytest.raises(RuntimeError):
        async with bus.scope():
            await bus.publish(_ready())
            raise RuntimeError("rollback")

    assert inner.published_events == []
    await bus.publish(_ready(2))  # outside any scope, so it goes straight through
    assert len(inner.published_events) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_flush_can_be_called_several_times_and_never_repeats_an_event() -> None:
    inner = InMemoryEventBus()
    bus = DeferredEventBus(inner)

    async with bus.scope() as scope:
        await bus.publish(_ready(1))
        await scope.flush()
        await scope.flush()
        await bus.publish(_ready(2))
        await scope.flush()

    assert len(inner.published_events) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_scope_only_buffers_the_events_of_its_own_request() -> None:
    inner = InMemoryEventBus()
    bus = DeferredEventBus(inner)

    async with bus.scope() as first:
        await bus.publish(_ready(1))
        async with bus.scope() as second:
            await bus.publish(_ready(2))
            await second.flush()
        assert len(inner.published_events) == 1  # only the inner scope's event
        await first.flush()

    assert len(inner.published_events) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_transaction_scope_on_a_plain_bus_publishes_immediately_and_flush_is_a_noop() -> None:
    plain: IEventBus = InMemoryEventBus()

    async with transaction_scope(plain) as scope:
        await plain.publish(_ready())
        await scope.flush()

    assert isinstance(plain, InMemoryEventBus)
    assert len(plain.published_events) == 1


# --- RelayEventBus ----------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_runs_local_subscribers_and_appends_to_the_stream() -> None:
    stream = FakeStream()
    relay = RelayEventBus(build_event_registry(), lambda: stream)
    seen: list[DomainEvent] = []

    async def handler(event: DocumentUploadedEvent) -> None:
        seen.append(event)

    relay.subscribe(DocumentUploadedEvent, handler)
    uploaded = DocumentUploadedEvent(document_id="d1", content_hash="h", filename="a.pdf")

    await relay.publish_all([uploaded, _ready()])

    assert seen == [uploaded]
    assert [e.type for e in stream.envelopes] == ["document.uploaded", "document.ready"]
    assert stream.closed == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_relay_without_a_stream_only_notifies_local_subscribers() -> None:
    relay = RelayEventBus(build_event_registry(), stream_factory=None)
    seen: list[DomainEvent] = []

    async def handler(event: DocumentReadyEvent) -> None:
        seen.append(event)

    relay.subscribe(DocumentReadyEvent, handler)
    await relay.publish(_ready())

    assert len(seen) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_stream_failure_is_swallowed_and_the_connection_is_still_closed() -> None:
    stream = FakeStream(fail=True)
    relay = RelayEventBus(build_event_registry(), lambda: stream)

    await relay.publish(_ready())  # must not raise

    assert stream.closed == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_failing_local_subscriber_is_not_hidden() -> None:
    relay = RelayEventBus(build_event_registry(), lambda: FakeStream())

    async def broken(event: DocumentReadyEvent) -> None:
        raise RuntimeError("could not queue the task")

    relay.subscribe(DocumentReadyEvent, broken)

    with pytest.raises(RuntimeError, match="could not queue"):
        await relay.publish(_ready())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_an_unregistered_event_is_logged_and_does_not_break_the_caller() -> None:
    stream = FakeStream()
    relay = RelayEventBus(build_event_registry(), lambda: stream)

    await relay.publish(DomainEvent())

    assert stream.envelopes == []
    assert stream.closed == 1
