"""Integration tests for the Redis Streams event log, using a real Redis (Testcontainers).

The producer and each consumer use their own connection, the way the worker and the API
processes would.
"""

import asyncio
import time
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime

import pytest
import redis.asyncio as aioredis
from testcontainers.community.redis import RedisContainer

from maritime.core.events.envelope import EventEnvelope
from maritime.core.events.stream import NEW_ENTRIES_ONLY, START_OF_STREAM
from maritime.infrastructure.events.redis_stream import RedisEventStream


def _envelope(n: int) -> EventEnvelope:
    return EventEnvelope(
        type="document.ready",
        event_id=f"event-{n}",
        occurred_at=datetime.now(UTC).isoformat(),
        payload={"document_id": f"doc-{n}", "chunk_count": n},
        traceparent=f"00-{n:032x}-{n:016x}-01",
    )


@pytest.fixture(scope="module")
def redis_url() -> Generator[str, None, None]:
    with RedisContainer("redis:7-alpine") as container:
        host, port = container.get_container_host_ip(), container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/2"


@pytest.fixture
async def streams(redis_url: str) -> AsyncGenerator[tuple[str, int], None]:
    key = f"test:events:{datetime.now(UTC).timestamp()}"
    yield key, 50
    client = aioredis.from_url(redis_url)
    await client.delete(key)
    await client.aclose()


def _stream(url: str, key: str, maxlen: int = 50) -> RedisEventStream:
    return RedisEventStream.from_url(url, key=key, maxlen=maxlen)


@pytest.mark.integration
async def test_an_entry_appended_by_one_connection_is_read_by_another(
    redis_url: str, streams: tuple[str, int]
) -> None:
    key, _ = streams
    producer, consumer = _stream(redis_url, key), _stream(redis_url, key)
    try:
        await producer.append(_envelope(1))

        entries = await consumer.read(START_OF_STREAM, block_ms=1000)

        assert len(entries) == 1
        assert entries[0].envelope is not None
        assert entries[0].envelope.event_id == "event-1"
        assert entries[0].envelope.payload == {"document_id": "doc-1", "chunk_count": 1}
        assert entries[0].envelope.traceparent == _envelope(1).traceparent
    finally:
        await producer.close()
        await consumer.close()


@pytest.mark.integration
async def test_a_blocked_reader_wakes_up_when_a_new_entry_arrives(
    redis_url: str, streams: tuple[str, int]
) -> None:
    key, _ = streams
    producer, consumer = _stream(redis_url, key), _stream(redis_url, key)
    try:
        waiting = asyncio.create_task(consumer.read(NEW_ENTRIES_ONLY, block_ms=5000))
        await asyncio.sleep(0.2)
        assert not waiting.done()

        await producer.append(_envelope(2))

        entries = await asyncio.wait_for(waiting, timeout=3)
        assert [e.envelope.event_id for e in entries if e.envelope] == ["event-2"]
    finally:
        await producer.close()
        await consumer.close()


@pytest.mark.integration
async def test_read_returns_nothing_when_the_wait_expires(
    redis_url: str, streams: tuple[str, int]
) -> None:
    key, _ = streams
    consumer = _stream(redis_url, key)
    try:
        assert await consumer.read(NEW_ENTRIES_ONLY, block_ms=200) == []
    finally:
        await consumer.close()


@pytest.mark.integration
async def test_an_idle_read_as_long_as_the_consumers_block_time_does_not_hit_the_socket_timeout(
    redis_url: str, streams: tuple[str, int]
) -> None:
    """Regression: redis-py's default socket timeout (5 s) equals the consumer's 5 s block time,
    so an idle read used to expire together with the socket and raise TimeoutError."""
    key, _ = streams
    consumer = _stream(redis_url, key)
    try:
        started = time.monotonic()

        assert await consumer.read(NEW_ENTRIES_ONLY, block_ms=5500) == []

        assert time.monotonic() - started >= 5.4  # it really waited longer than the old default
    finally:
        await consumer.close()


@pytest.mark.integration
async def test_every_consumer_receives_every_entry(
    redis_url: str, streams: tuple[str, int]
) -> None:
    key, _ = streams
    producer = _stream(redis_url, key)
    consumers = [_stream(redis_url, key) for _ in range(3)]
    try:
        for n in range(4):
            await producer.append(_envelope(n))

        results = [await c.read(START_OF_STREAM, block_ms=1000) for c in consumers]

        for entries in results:
            assert [e.envelope.event_id for e in entries if e.envelope] == [
                "event-0",
                "event-1",
                "event-2",
                "event-3",
            ]
    finally:
        await producer.close()
        for c in consumers:
            await c.close()


@pytest.mark.integration
async def test_replay_returns_only_entries_after_the_given_id(
    redis_url: str, streams: tuple[str, int]
) -> None:
    key, _ = streams
    stream = _stream(redis_url, key)
    try:
        ids = [await stream.append(_envelope(n)) for n in range(5)]

        replayed = await stream.replay(ids[1])

        assert [e.stream_id for e in replayed] == ids[2:]
        assert await stream.replay(ids[-1]) == []
    finally:
        await stream.close()


@pytest.mark.integration
async def test_the_log_is_trimmed_to_maxlen_keeping_the_newest(
    redis_url: str, streams: tuple[str, int]
) -> None:
    key, _ = streams
    stream = _stream(redis_url, key, maxlen=10)
    try:
        for n in range(25):
            await stream.append(_envelope(n))

        kept = await stream.replay(START_OF_STREAM)

        assert [e.envelope.event_id for e in kept if e.envelope] == [
            f"event-{n}" for n in range(15, 25)
        ]
    finally:
        await stream.close()


@pytest.mark.integration
async def test_an_unreadable_entry_is_returned_empty_and_does_not_block_the_next_ones(
    redis_url: str, streams: tuple[str, int]
) -> None:
    key, _ = streams
    stream = _stream(redis_url, key)
    raw = aioredis.from_url(redis_url, decode_responses=True)
    try:
        await raw.xadd(key, {"data": "this is not json"})
        await raw.xadd(key, {"unexpected": "field"})
        await stream.append(_envelope(7))

        entries = await stream.read(START_OF_STREAM, block_ms=1000)

        assert [e.envelope is None for e in entries] == [True, True, False]
        assert entries[-1].envelope is not None
        assert entries[-1].envelope.event_id == "event-7"
    finally:
        await raw.aclose()
        await stream.close()
