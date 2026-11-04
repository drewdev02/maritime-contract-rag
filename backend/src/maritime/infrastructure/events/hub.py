import asyncio
import contextlib
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from opentelemetry import propagate

from maritime.core.events.envelope import EventEnvelope
from maritime.core.events.stream import IEventStream, StreamEntry
from maritime.core.telemetry.logging import get_logger
from maritime.core.telemetry.tracer import get_tracer

logger = get_logger(__name__)

_STREAM_ID = re.compile(r"^\d+-\d+$")


def stream_id_key(stream_id: str) -> tuple[int, int]:
    """Orders Redis stream ids (``<ms>-<seq>``) numerically."""
    millis, _, seq = stream_id.partition("-")
    return int(millis), int(seq or 0)


def is_stream_id(value: str | None) -> bool:
    return bool(value and _STREAM_ID.match(value))


@dataclass(frozen=True, slots=True)
class BroadcastItem:
    stream_id: str
    envelope: EventEnvelope


@dataclass(eq=False)
class Subscription:
    """One connected client. ``None`` in the queue is the signal to end the stream."""

    queue: "asyncio.Queue[BroadcastItem | None]"
    overflowed: bool = field(default=False)


class EventBroadcaster:
    """Fans events out to every client connected to this API process.

    A client that cannot keep up is not allowed to hold memory: its queue is dropped, it is flagged
    and its stream ends. The browser reconnects with ``Last-Event-ID`` and the missed events are
    replayed from the Redis stream, so nothing is lost and nobody blocks the others.
    """

    def __init__(self, max_pending: int = 100) -> None:
        self._max_pending = max_pending
        self._subscriptions: set[Subscription] = set()

    @contextmanager
    def subscribe(self) -> Iterator[Subscription]:
        subscription = Subscription(queue=asyncio.Queue(maxsize=self._max_pending))
        self._subscriptions.add(subscription)
        try:
            yield subscription
        finally:
            self._subscriptions.discard(subscription)

    def publish(self, item: BroadcastItem) -> None:
        for subscription in list(self._subscriptions):
            try:
                subscription.queue.put_nowait(item)
            except asyncio.QueueFull:
                self._drop(subscription)

    def close(self) -> None:
        """Ends every open stream (used on shutdown so connections do not outlive the server)."""
        for subscription in list(self._subscriptions):
            self._drop(subscription)

    @property
    def clients(self) -> int:
        return len(self._subscriptions)

    @staticmethod
    def _drop(subscription: Subscription) -> None:
        subscription.overflowed = True
        while not subscription.queue.empty():
            subscription.queue.get_nowait()
        subscription.queue.put_nowait(None)


class StreamConsumer:
    """Reads the shared event stream and hands each event to the broadcaster.

    It starts from the stream's current tail and then always advances with concrete ids, so no
    entry is skipped between reads. If Redis fails it keeps its position, backs off and resumes,
    which also covers the events produced while it was away.
    """

    def __init__(
        self,
        stream_factory: Callable[[], IEventStream],
        broadcaster: EventBroadcaster,
        block_ms: int = 5000,
        retry_delay: float = 1.0,
    ) -> None:
        self._stream_factory = stream_factory
        self._broadcaster = broadcaster
        self._block_ms = block_ms
        self._retry_delay = retry_delay
        self.ready = asyncio.Event()  # set once the starting position in the stream is known

    async def run(self) -> None:
        stream: IEventStream | None = None
        last_id: str | None = None
        try:
            while True:
                try:
                    stream = stream or self._stream_factory()
                    if last_id is None:
                        last_id = await stream.tail_id()
                        self.ready.set()
                    for entry in await stream.read(last_id, block_ms=self._block_ms):
                        last_id = entry.stream_id
                        if entry.envelope is not None:
                            self._deliver(entry.stream_id, entry.envelope)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.warning("Event stream read failed; retrying", exc_info=True)
                    await self._close(stream)
                    stream = None
                    await asyncio.sleep(self._retry_delay)
        finally:
            await self._close(stream)

    def _deliver(self, stream_id: str, envelope: EventEnvelope) -> None:
        """Hands the event to the connected clients inside a span that continues the publisher's
        trace, so one trace follows a document from the upload to the notification."""
        parent = (
            propagate.extract({"traceparent": envelope.traceparent})
            if envelope.traceparent
            else None
        )
        with get_tracer("maritime.events").start_as_current_span(
            "event.consume",
            context=parent,
            attributes={
                "event.type": envelope.type,
                "event.id": envelope.event_id,
                "event.clients": self._broadcaster.clients,
            },
        ):
            self._broadcaster.publish(BroadcastItem(stream_id, envelope))

    @staticmethod
    async def _close(stream: IEventStream | None) -> None:
        if stream is not None:
            with contextlib.suppress(Exception):
                await stream.close()


class EventHub:
    """The API process's side of the event stream: one consumer task plus the broadcaster."""

    def __init__(self, stream_factory: Callable[[], IEventStream], max_pending: int = 100) -> None:
        self._stream_factory = stream_factory
        self.broadcaster = EventBroadcaster(max_pending=max_pending)
        self._consumer = StreamConsumer(stream_factory, self.broadcaster)
        self._task: asyncio.Task[None] | None = None

    async def start(self, ready_timeout: float = 3.0) -> None:
        """Starts the consumer and waits (briefly) until it knows where in the stream it begins.

        Without that wait an event published right after startup could fall before the starting
        position. If Redis is unavailable the API still starts; the consumer keeps retrying.
        """
        self._task = asyncio.create_task(self._consumer.run(), name="event-stream-consumer")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._consumer.ready.wait(), ready_timeout)

    async def stop(self) -> None:
        self.broadcaster.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def replay(self, after_id: str, count: int = 1000) -> list[StreamEntry]:
        """Events already stored after ``after_id`` (for a client that reconnects)."""
        stream = self._stream_factory()
        try:
            return await stream.replay(after_id, count=count)
        finally:
            await stream.close()
