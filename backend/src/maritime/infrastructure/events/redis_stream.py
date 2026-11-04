from typing import Any

import redis.asyncio as aioredis

from maritime.core.events.envelope import EventEnvelope
from maritime.core.events.stream import START_OF_STREAM, IEventStream, StreamEntry
from maritime.core.exceptions import EventDecodeError
from maritime.core.telemetry.logging import get_logger

logger = get_logger(__name__)

_FIELD = "data"


class RedisEventStream(IEventStream):
    """Redis Streams implementation of the event log.

    The log is trimmed to ``maxlen`` entries on every append (exact trimming: the volume is a few
    events per document, so the cost is negligible and the bound is deterministic).
    """

    def __init__(self, client: aioredis.Redis, key: str, maxlen: int = 10_000) -> None:
        self._client = client
        self._key = key
        self._maxlen = maxlen

    # A blocking read (XREAD BLOCK) legitimately sits idle for up to its ``block_ms``. redis-py's
    # default socket timeout is 5 s, which equals the consumer's block time, so an idle read could
    # expire together with the socket and surface as a TimeoutError. The socket timeout must be
    # comfortably longer than any block time.
    SOCKET_TIMEOUT_SECONDS = 30.0
    CONNECT_TIMEOUT_SECONDS = 5.0

    @classmethod
    def from_url(cls, url: str, key: str, maxlen: int = 10_000) -> "RedisEventStream":
        client = aioredis.from_url(
            url,
            decode_responses=True,
            socket_timeout=cls.SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=cls.CONNECT_TIMEOUT_SECONDS,
        )
        return cls(client, key=key, maxlen=maxlen)

    async def append(self, envelope: EventEnvelope) -> str:
        stream_id = await self._client.xadd(
            self._key, {_FIELD: envelope.to_json()}, maxlen=self._maxlen, approximate=False
        )
        return str(stream_id)

    async def read(self, last_id: str, block_ms: int = 5000, count: int = 100) -> list[StreamEntry]:
        # redis-py types these replies loosely; with decode_responses=True they are str-based.
        response: Any = await self._client.xread({self._key: last_id}, count=count, block=block_ms)
        entries: list[tuple[str, dict[str, str]]] = []
        for _stream, items in response or []:
            entries.extend(items)
        return [self._to_entry(stream_id, fields) for stream_id, fields in entries]

    async def replay(self, after_id: str, count: int = 1000) -> list[StreamEntry]:
        items: Any = await self._client.xrange(self._key, min=f"({after_id}", max="+", count=count)
        return [self._to_entry(stream_id, fields) for stream_id, fields in items]

    async def tail_id(self) -> str:
        newest: Any = await self._client.xrevrange(self._key, count=1)
        return str(newest[0][0]) if newest else START_OF_STREAM

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _to_entry(stream_id: str, fields: dict[str, Any]) -> StreamEntry:
        try:
            return StreamEntry(stream_id, EventEnvelope.from_json(fields[_FIELD]))
        except (KeyError, EventDecodeError):
            logger.warning("Skipping unreadable stream entry", extra={"stream_id": stream_id})
            return StreamEntry(stream_id, None)
