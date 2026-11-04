import dataclasses
from datetime import datetime

from maritime.core.domain.events import DomainEvent
from maritime.core.events.envelope import ENVELOPE_VERSION, EventEnvelope
from maritime.core.exceptions import EventDecodeError
from maritime.core.telemetry.logging import get_logger

logger = get_logger(__name__)

_BASE_FIELDS = frozenset({"event_id", "occurred_at"})


class EventRegistry:
    """Maps stable event names to domain event classes and converts them to and from envelopes."""

    def __init__(self) -> None:
        self._by_name: dict[str, type[DomainEvent]] = {}
        self._by_class: dict[type[DomainEvent], str] = {}

    def register(self, name: str, event_type: type[DomainEvent]) -> None:
        if name in self._by_name or event_type in self._by_class:
            raise ValueError(f"Event already registered: {name} / {event_type.__name__}")
        self._by_name[name] = event_type
        self._by_class[event_type] = name

    def encode(self, event: DomainEvent, traceparent: str | None = None) -> EventEnvelope:
        name = self._by_class.get(type(event))
        if name is None:
            raise EventDecodeError(f"Event type is not registered: {type(event).__name__}")
        payload = {
            f.name: getattr(event, f.name)
            for f in dataclasses.fields(event)
            if f.name not in _BASE_FIELDS
        }
        return EventEnvelope(
            type=name,
            event_id=event.event_id,
            occurred_at=event.occurred_at.isoformat(),
            payload=payload,
            traceparent=traceparent,
        )

    def decode(self, envelope: EventEnvelope) -> DomainEvent | None:
        """Rebuilds the event, or returns ``None`` when this consumer cannot understand it.

        Unknown names and newer envelope versions are skipped (logged) so that a producer deployed
        before its consumers never breaks them. A known event with a broken payload raises.
        """
        event_type = self._by_name.get(envelope.type)
        if event_type is None:
            logger.warning("Ignoring unknown event type", extra={"event_type": envelope.type})
            return None
        if envelope.version > ENVELOPE_VERSION:
            logger.warning(
                "Ignoring event with a newer envelope version",
                extra={"event_type": envelope.type, "event_version": envelope.version},
            )
            return None

        expected = {f.name for f in dataclasses.fields(event_type)} - _BASE_FIELDS
        missing = expected - envelope.payload.keys()
        if missing:
            raise EventDecodeError(
                f"Event '{envelope.type}' is missing fields: {', '.join(sorted(missing))}"
            )
        try:
            return event_type(
                event_id=envelope.event_id,
                occurred_at=datetime.fromisoformat(envelope.occurred_at),
                **{name: envelope.payload[name] for name in expected},
            )
        except (ValueError, TypeError) as exc:
            raise EventDecodeError(f"Event '{envelope.type}' could not be rebuilt") from exc
