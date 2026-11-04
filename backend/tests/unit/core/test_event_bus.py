from dataclasses import dataclass

import pytest

from maritime.core.domain.events import DomainEvent
from maritime.core.events.in_memory import InMemoryEventBus


@dataclass(frozen=True, slots=True)
class EventA(DomainEvent):
    msg: str


@dataclass(frozen=True, slots=True)
class EventB(DomainEvent):
    num: int


@pytest.mark.unit
@pytest.mark.asyncio
async def test_in_memory_event_bus_dispatches_to_handlers() -> None:
    bus = InMemoryEventBus()
    received_a: list[EventA] = []
    received_b: list[EventB] = []

    async def handle_a(event: EventA) -> None:
        received_a.append(event)

    async def handle_b(event: EventB) -> None:
        received_b.append(event)

    bus.subscribe(EventA, handle_a)
    bus.subscribe(EventB, handle_b)

    event_a = EventA(msg="test_a")
    event_b = EventB(num=42)

    await bus.publish(event_a)
    await bus.publish(event_b)

    assert received_a == [event_a]
    assert received_b == [event_b]
    assert bus.published_events == [event_a, event_b]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_in_memory_event_bus_publish_all_and_clear_history() -> None:
    bus = InMemoryEventBus()
    calls: list[str] = []

    async def handle_a1(event: EventA) -> None:
        calls.append(f"handler1:{event.msg}")

    async def handle_a2(event: EventA) -> None:
        calls.append(f"handler2:{event.msg}")

    bus.subscribe(EventA, handle_a1)
    bus.subscribe(EventA, handle_a2)

    events = [EventA(msg="1"), EventA(msg="2")]
    await bus.publish_all(events)

    assert calls == ["handler1:1", "handler2:1", "handler1:2", "handler2:2"]
    assert len(bus.published_events) == 2

    bus.clear_history()
    assert len(bus.published_events) == 0
