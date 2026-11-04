import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from maritime.core.events.envelope import EventEnvelope
from maritime.core.events.stream import IEventStream, StreamEntry
from maritime.infrastructure.events.hub import (
    BroadcastItem,
    EventBroadcaster,
    EventHub,
    StreamConsumer,
    is_stream_id,
    stream_id_key,
)
from maritime.modules.ingestion.presentation.events_router import (
    document_event_stream,
    format_sse,
)


def _envelope(n: int, type_: str = "document.ready") -> EventEnvelope:
    return EventEnvelope(
        type=type_,
        event_id=f"e{n}",
        occurred_at=datetime.now(UTC).isoformat(),
        payload={"document_id": f"d{n}", "chunk_count": n},
    )


def _item(n: int) -> BroadcastItem:
    return BroadcastItem(f"{n}-0", _envelope(n))


class ScriptedStream(IEventStream):
    """A stream that serves scripted reads, so the consumer's behaviour can be observed."""

    def __init__(self, script: list[Any], stored: list[StreamEntry] | None = None) -> None:
        self.script = list(script)
        self.stored = stored or []
        self.read_from: list[str] = []
        self.closed = 0

    async def append(self, envelope: EventEnvelope) -> str:
        raise NotImplementedError

    async def read(self, last_id: str, block_ms: int = 5000, count: int = 100) -> list[StreamEntry]:
        self.read_from.append(last_id)
        if not self.script:
            await asyncio.sleep(3600)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return list(step)

    async def replay(self, after_id: str, count: int = 1000) -> list[StreamEntry]:
        return [e for e in self.stored if stream_id_key(e.stream_id) > stream_id_key(after_id)]

    async def tail_id(self) -> str:
        return "10-0"

    async def close(self) -> None:
        self.closed += 1


async def _drain(gen: AsyncIterator[str], count: int) -> list[str]:
    return [await asyncio.wait_for(anext(gen), timeout=2) for _ in range(count)]


# --- ids ---------------------------------------------------------------------------------------


@pytest.mark.unit
def test_stream_ids_are_ordered_numerically_not_alphabetically() -> None:
    assert stream_id_key("9-0") < stream_id_key("10-0")
    assert stream_id_key("10-1") > stream_id_key("10-0")
    assert is_stream_id("1700000000000-0")
    assert not is_stream_id("latest") and not is_stream_id(None) and not is_stream_id("1-")


# --- EventBroadcaster --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_every_connected_client_gets_every_event_and_leavers_stop_receiving() -> None:
    broadcaster = EventBroadcaster()

    with broadcaster.subscribe() as first:
        with broadcaster.subscribe() as second:
            assert broadcaster.clients == 2
            one, two = _item(1), _item(2)
            broadcaster.publish(one)
            assert first.queue.get_nowait() is one
            assert second.queue.get_nowait() is one

        assert broadcaster.clients == 1
        broadcaster.publish(two)
        assert first.queue.get_nowait() is two

    assert broadcaster.clients == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_client_that_cannot_keep_up_is_dropped_without_blocking_the_others() -> None:
    broadcaster = EventBroadcaster(max_pending=2)

    with broadcaster.subscribe() as slow, broadcaster.subscribe() as fast:
        for n in range(1, 4):
            broadcaster.publish(_item(n))
            if not fast.queue.empty():
                fast.queue.get_nowait()

        assert slow.overflowed is True
        assert await slow.queue.get() is None  # the signal to end its stream
        assert fast.overflowed is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_closing_the_broadcaster_ends_every_open_stream() -> None:
    broadcaster = EventBroadcaster()
    with broadcaster.subscribe() as client:
        broadcaster.close()
        assert await client.queue.get() is None


# --- StreamConsumer ----------------------------------------------------------------------------


async def _run_until(consumer: StreamConsumer, condition: Callable[[], bool]) -> None:
    task = asyncio.create_task(consumer.run())
    try:
        for _ in range(200):
            if condition():
                return
            await asyncio.sleep(0.01)
        raise AssertionError("condition not reached")
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_consumer_starts_from_the_tail_and_always_advances_with_concrete_ids() -> None:
    stream = ScriptedStream(
        [
            [],  # a read that times out must not make it fall back to "new entries only"
            [StreamEntry("11-0", _envelope(1)), StreamEntry("12-0", None)],
            [StreamEntry("13-0", _envelope(3))],
        ]
    )
    broadcaster = EventBroadcaster()
    received: list[str] = []
    consumer = StreamConsumer(lambda: stream, broadcaster, retry_delay=0.01)

    with broadcaster.subscribe() as client:
        task_done = asyncio.Event()

        async def collect() -> None:
            while len(received) < 2:
                item = await client.queue.get()
                assert item is not None
                received.append(item.stream_id)
            task_done.set()

        collector = asyncio.create_task(collect())
        await _run_until(consumer, task_done.is_set)
        await collector

    assert received == ["11-0", "13-0"]  # the unreadable 12-0 was skipped, not delivered
    # Each read continues from the last entry seen (even an unreadable one); the empty read keeps
    # the same position instead of falling back to "new entries only".
    assert stream.read_from[:3] == ["10-0", "10-0", "12-0"]
    assert "$" not in stream.read_from


@pytest.mark.unit
@pytest.mark.asyncio
async def test_consumer_survives_redis_failures_and_resumes_from_where_it_was() -> None:
    first = ScriptedStream([[StreamEntry("11-0", _envelope(1))], ConnectionError("redis down")])
    second = ScriptedStream([[StreamEntry("12-0", _envelope(2))]])
    streams = [first, second]
    broadcaster = EventBroadcaster()
    consumer = StreamConsumer(lambda: streams.pop(0), broadcaster, retry_delay=0.01)
    received: list[str] = []

    with broadcaster.subscribe() as client:

        async def collect() -> None:
            while len(received) < 2:
                item = await client.queue.get()
                assert item is not None
                received.append(item.stream_id)

        collector = asyncio.create_task(collect())
        await _run_until(consumer, lambda: len(received) >= 2)
        await collector

    assert received == ["11-0", "12-0"]
    assert second.read_from[0] == "11-0"  # resumed, so nothing produced during the outage is lost
    assert first.closed >= 1


# --- SSE ---------------------------------------------------------------------------------------


@pytest.mark.unit
def test_sse_frame_carries_the_stream_id_the_type_and_a_flat_json_payload() -> None:
    frame = format_sse(BroadcastItem("17-3", _envelope(2)))

    lines = frame.strip().split("\n")
    assert lines[0] == "id: 17-3"
    assert lines[1] == "event: document.ready"
    data = json.loads(lines[2].removeprefix("data: "))
    assert data["type"] == "document.ready"
    assert (data["document_id"], data["chunk_count"], data["event_id"]) == ("d2", 2, "e2")
    assert frame.endswith("\n\n")


def _hub(stored: list[StreamEntry] | None = None) -> EventHub:
    return EventHub(lambda: ScriptedStream([], stored))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_new_client_gets_live_events_after_the_retry_hint() -> None:
    hub = _hub()
    gen = document_event_stream(hub, last_event_id=None, heartbeat_seconds=5)

    assert (await _drain(gen, 1))[0] == "retry: 3000\n\n"
    hub.broadcaster.publish(_item(5))
    frame = (await _drain(gen, 1))[0]

    assert frame.startswith("id: 5-0\nevent: document.ready")
    await gen.aclose()
    assert hub.broadcaster.clients == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_reconnecting_client_is_replayed_what_it_missed_and_never_gets_duplicates() -> None:
    stored = [StreamEntry(f"{n}-0", _envelope(n)) for n in range(1, 6)]
    hub = _hub(stored)
    gen = document_event_stream(hub, last_event_id="2-0", heartbeat_seconds=5)

    await _drain(gen, 1)  # retry hint; subscribes the client
    hub.broadcaster.publish(_item(4))  # arrives live while the replay is read: already replayed
    hub.broadcaster.publish(_item(6))  # genuinely new
    frames = await _drain(gen, 4)

    assert [f.split("\n")[0] for f in frames] == ["id: 3-0", "id: 4-0", "id: 5-0", "id: 6-0"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_garbage_last_event_id_is_ignored_instead_of_failing() -> None:
    hub = _hub([StreamEntry("1-0", _envelope(1))])
    gen = document_event_stream(hub, last_event_id="not-an-id; DROP", heartbeat_seconds=5)

    await _drain(gen, 1)
    hub.broadcaster.publish(_item(9))

    assert (await _drain(gen, 1))[0].startswith("id: 9-0")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_idle_connections_get_a_keep_alive_comment() -> None:
    gen = document_event_stream(_hub(), last_event_id=None, heartbeat_seconds=0.05)

    frames = await _drain(gen, 3)

    assert frames[1:] == [": keep-alive\n\n", ": keep-alive\n\n"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_stream_ends_when_the_client_was_dropped_so_it_can_reconnect() -> None:
    hub = _hub()
    gen = document_event_stream(hub, last_event_id=None, heartbeat_seconds=5)
    await _drain(gen, 1)

    hub.broadcaster.close()

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(gen), timeout=2)


# --- tracing -----------------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_consuming_an_event_continues_the_trace_of_the_publisher() -> None:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from maritime.core.telemetry.tracer import setup_telemetry

    setup_telemetry(service_name="maritime-test")
    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    trace_id, span_id = "0af7651916cd43dd8448eb211c80319c", "b7ad6b7169203331"
    envelope = EventEnvelope(
        type="document.ready",
        event_id="e1",
        occurred_at=datetime.now(UTC).isoformat(),
        payload={"document_id": "d1", "chunk_count": 1},
        traceparent=f"00-{trace_id}-{span_id}-01",
    )
    broadcaster = EventBroadcaster()
    consumer = StreamConsumer(
        lambda: ScriptedStream([[StreamEntry("11-0", envelope)]]), broadcaster
    )

    with broadcaster.subscribe() as client:
        await _run_until(consumer, lambda: not client.queue.empty())

    (consume,) = [s for s in exporter.get_finished_spans() if s.name == "event.consume"]
    assert format(consume.context.trace_id, "032x") == trace_id
    assert consume.parent is not None
    assert format(consume.parent.span_id, "016x") == span_id
    assert consume.attributes is not None
    assert consume.attributes["event.type"] == "document.ready"
    assert consume.attributes["event.clients"] == 1
