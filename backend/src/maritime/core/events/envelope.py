import json
from dataclasses import dataclass
from typing import Any

from maritime.core.exceptions import EventDecodeError

ENVELOPE_VERSION = 1


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Wire format of a domain event that travels between processes.

    ``type`` is a stable name (for example ``document.ready``), never a Python class path, so the
    producer and the consumer can be deployed and refactored independently. ``version`` allows the
    payload to evolve: a consumer ignores envelopes newer than the ones it understands.
    ``traceparent`` carries the W3C trace context so a trace can continue across the stream.
    """

    type: str
    event_id: str
    occurred_at: str
    payload: dict[str, Any]
    version: int = ENVELOPE_VERSION
    traceparent: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type,
                "version": self.version,
                "event_id": self.event_id,
                "occurred_at": self.occurred_at,
                "payload": self.payload,
                "traceparent": self.traceparent,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, raw: str | bytes) -> "EventEnvelope":
        try:
            data = json.loads(raw)
            return cls(
                type=str(data["type"]),
                event_id=str(data["event_id"]),
                occurred_at=str(data["occurred_at"]),
                payload=dict(data["payload"]),
                version=int(data.get("version", 1)),
                traceparent=data.get("traceparent"),
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise EventDecodeError(f"Malformed event envelope: {type(exc).__name__}") from exc
