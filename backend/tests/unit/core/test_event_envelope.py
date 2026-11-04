import json
from datetime import UTC, datetime

import pytest

from maritime.core.events.envelope import EventEnvelope
from maritime.core.exceptions import EventDecodeError
from maritime.infrastructure.event_registry import build_event_registry
from maritime.modules.ingestion.domain.events import (
    DocumentFailedEvent,
    DocumentProcessingStartedEvent,
    DocumentReadyEvent,
    DocumentUploadedEvent,
)

registry = build_event_registry()

EVENTS = [
    DocumentUploadedEvent(document_id="d1", content_hash="h" * 64, filename="a.pdf"),
    DocumentProcessingStartedEvent(document_id="d1"),
    DocumentReadyEvent(document_id="d1", chunk_count=7),
    DocumentFailedEvent(document_id="d1", reason="Archivo corrupto o sin páginas legibles"),
]


@pytest.mark.unit
@pytest.mark.parametrize("event", EVENTS, ids=lambda e: type(e).__name__)
def test_every_event_survives_a_wire_round_trip(event: object) -> None:
    assert isinstance(
        event,
        DocumentUploadedEvent
        | DocumentProcessingStartedEvent
        | DocumentReadyEvent
        | DocumentFailedEvent,
    )

    wire = registry.encode(event, traceparent="00-aa-bb-01").to_json()
    decoded = registry.decode(EventEnvelope.from_json(wire))

    assert decoded == event
    assert decoded is not None
    assert decoded.event_id == event.event_id
    assert decoded.occurred_at == event.occurred_at
    assert decoded.occurred_at.tzinfo is not None


@pytest.mark.unit
def test_wire_names_are_stable_strings_not_class_paths() -> None:
    envelope = registry.encode(DocumentReadyEvent(document_id="d1", chunk_count=3))

    assert envelope.type == "document.ready"
    assert envelope.payload == {"document_id": "d1", "chunk_count": 3}
    assert "maritime" not in envelope.to_json()


@pytest.mark.unit
def test_traceparent_travels_in_the_envelope() -> None:
    envelope = registry.encode(DocumentReadyEvent(document_id="d1", chunk_count=1), "00-x-y-01")

    assert EventEnvelope.from_json(envelope.to_json()).traceparent == "00-x-y-01"


@pytest.mark.unit
def test_unknown_event_type_is_skipped_not_fatal() -> None:
    envelope = EventEnvelope(
        type="document.archived",
        event_id="e1",
        occurred_at=datetime.now(UTC).isoformat(),
        payload={},
    )

    assert registry.decode(envelope) is None


@pytest.mark.unit
def test_newer_envelope_version_is_skipped_not_fatal() -> None:
    envelope = EventEnvelope(
        type="document.ready",
        event_id="e1",
        occurred_at=datetime.now(UTC).isoformat(),
        payload={"document_id": "d1", "chunk_count": 1},
        version=99,
    )

    assert registry.decode(envelope) is None


@pytest.mark.unit
def test_extra_payload_fields_are_ignored_for_forward_compatibility() -> None:
    envelope = EventEnvelope(
        type="document.ready",
        event_id="e1",
        occurred_at=datetime.now(UTC).isoformat(),
        payload={"document_id": "d1", "chunk_count": 2, "pages": 9},
    )

    assert registry.decode(envelope) == DocumentReadyEvent(
        event_id="e1",
        occurred_at=datetime.fromisoformat(envelope.occurred_at),
        document_id="d1",
        chunk_count=2,
    )


@pytest.mark.unit
def test_missing_payload_field_is_an_error() -> None:
    envelope = EventEnvelope(
        type="document.ready",
        event_id="e1",
        occurred_at=datetime.now(UTC).isoformat(),
        payload={"document_id": "d1"},
    )

    with pytest.raises(EventDecodeError, match="chunk_count"):
        registry.decode(envelope)


@pytest.mark.unit
@pytest.mark.parametrize("raw", ["not json", "[]", json.dumps({"type": "x"}), b"\xff\xfe"])
def test_malformed_envelopes_raise_a_typed_error(raw: str | bytes) -> None:
    with pytest.raises(EventDecodeError):
        EventEnvelope.from_json(raw)


@pytest.mark.unit
def test_encoding_an_unregistered_event_is_an_error() -> None:
    from maritime.core.domain.events import DomainEvent

    with pytest.raises(EventDecodeError, match="not registered"):
        registry.encode(DomainEvent())
