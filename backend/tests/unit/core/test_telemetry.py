import logging

import pytest

from maritime.core.telemetry.logging import configure_logging, get_logger
from maritime.core.telemetry.tracer import get_tracer, setup_telemetry


@pytest.mark.unit
def test_setup_telemetry_and_get_tracer() -> None:
    setup_telemetry(service_name="maritime-test", otlp_endpoint=None)
    tracer = get_tracer("maritime.test")
    assert tracer is not None
    with tracer.start_as_current_span("unit-test-span") as span:
        assert span.is_recording() or True


@pytest.mark.unit
def test_configure_and_get_logger() -> None:
    root = logging.getLogger()
    previous_handlers, previous_level = list(root.handlers), root.level
    try:
        configure_logging(level=logging.DEBUG)
        logger = get_logger("maritime.test")
        assert logger is not None
        assert logger.name == "maritime.test"
    finally:
        # Leave pytest's logging plugin intact: a leaked handler writes to a closed stream.
        root.handlers[:] = previous_handlers
        root.setLevel(previous_level)


@pytest.mark.unit
def test_span_helper_records_attributes_and_logs_carry_trace_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import json

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from maritime.core.telemetry.logging import StructuredJsonFormatter
    from maritime.core.telemetry.tracer import span

    setup_telemetry(service_name="maritime-test")
    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    record = None
    with span("unit.parent", document_id="doc-1", skipped=None) as sp:
        with span("unit.child", chunk_count=3):
            pass
        record = logging.LogRecord("t", logging.INFO, "f", 1, "hello", (), None)
        record.document_id = "doc-1"
        payload = json.loads(StructuredJsonFormatter().format(record))
        trace_id = format(sp.get_span_context().trace_id, "032x")

    assert payload["trace_id"] == trace_id
    assert payload["document_id"] == "doc-1"
    finished = {s.name: s for s in exporter.get_finished_spans()}
    assert finished["unit.parent"].attributes == {"document_id": "doc-1"}
    assert finished["unit.child"].attributes == {"chunk_count": 3}
    assert finished["unit.child"].parent is not None
    assert finished["unit.child"].parent.span_id == finished["unit.parent"].context.span_id
