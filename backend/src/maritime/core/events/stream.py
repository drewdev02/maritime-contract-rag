from abc import ABC, abstractmethod
from dataclasses import dataclass

from maritime.core.events.envelope import EventEnvelope

START_OF_STREAM = "0-0"
NEW_ENTRIES_ONLY = "$"


@dataclass(frozen=True, slots=True)
class StreamEntry:
    """One entry read from the stream.

    ``envelope`` is ``None`` when the entry could not be parsed. It is still returned so a consumer
    can advance past it instead of re-reading (and failing on) the same entry forever.
    """

    stream_id: str
    envelope: EventEnvelope | None


class IEventStream(ABC):
    """Port for an append-only, ordered event log shared by several processes.

    Every consumer reads the whole log independently (broadcast), tracking its own position with the
    ``stream_id`` of the last entry it handled. That position also lets a client that was
    disconnected resume exactly where it stopped.
    """

    @abstractmethod
    async def append(self, envelope: EventEnvelope) -> str:
        """Appends an envelope and returns its stream id."""
        pass

    @abstractmethod
    async def read(self, last_id: str, block_ms: int = 5000, count: int = 100) -> list[StreamEntry]:
        """Waits up to ``block_ms`` for entries after ``last_id`` (``NEW_ENTRIES_ONLY`` for new ones)."""
        pass

    @abstractmethod
    async def replay(self, after_id: str, count: int = 1000) -> list[StreamEntry]:
        """Returns the entries after ``after_id`` that are already stored, without waiting."""
        pass

    @abstractmethod
    async def tail_id(self) -> str:
        """Id of the newest entry, or ``START_OF_STREAM`` when the log is empty.

        A consumer that only wants new entries must start from this concrete id instead of
        reading with ``NEW_ENTRIES_ONLY`` every time: entries appended between two reads would be
        skipped.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Releases the underlying connection."""
        pass
