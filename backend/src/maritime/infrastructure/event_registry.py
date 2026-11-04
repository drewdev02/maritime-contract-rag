from maritime.core.events.registry import EventRegistry
from maritime.modules.ingestion.domain.events import register_ingestion_events


def build_event_registry() -> EventRegistry:
    """Registry with every event type that may cross a process boundary."""
    registry = EventRegistry()
    register_ingestion_events(registry)
    return registry
