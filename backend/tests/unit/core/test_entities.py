from dataclasses import dataclass
from datetime import UTC
from uuid import UUID

import pytest

from maritime.core.domain.entity import AggregateRoot, Entity
from maritime.core.domain.events import DomainEvent


@dataclass(frozen=True, slots=True)
class DummyEvent(DomainEvent):
    payload: str


class DummyEntity(Entity[str]):
    def __init__(self, id: str, name: str) -> None:
        super().__init__(id=id)
        self.name = name


class AnotherEntity(Entity[str]):
    def __init__(self, id: str) -> None:
        super().__init__(id=id)


class DummyAggregate(AggregateRoot[str]):
    def __init__(self, id: str) -> None:
        super().__init__(id=id)

    def do_action(self, msg: str) -> None:
        self.record_event(DummyEvent(payload=msg))


@pytest.mark.unit
def test_domain_event_has_id_and_utc_timestamp() -> None:
    event = DummyEvent(payload="test")
    assert event.payload == "test"
    assert event.event_id is not None
    # Verify event_id is a valid UUID string
    UUID(event.event_id)
    assert event.occurred_at is not None
    assert event.occurred_at.tzinfo == UTC


@pytest.mark.unit
def test_entity_equality_by_id_and_type() -> None:
    e1 = DummyEntity(id="123", name="first")
    e2 = DummyEntity(id="123", name="second")
    e3 = DummyEntity(id="456", name="first")
    e_other = AnotherEntity(id="123")

    assert e1 == e2
    assert hash(e1) == hash(e2)
    assert e1 != e3
    assert e1 != e_other
    assert e1 != "not an entity"


@pytest.mark.unit
def test_aggregate_root_records_and_pulls_events() -> None:
    agg = DummyAggregate(id="agg-1")
    assert len(agg.pull_events()) == 0

    agg.do_action("hello")
    agg.do_action("world")

    events = agg.pull_events()
    assert len(events) == 2
    assert isinstance(events[0], DummyEvent)
    assert events[0].payload == "hello"
    assert isinstance(events[1], DummyEvent)
    assert events[1].payload == "world"

    # Subsequent pull should be empty
    assert len(agg.pull_events()) == 0
