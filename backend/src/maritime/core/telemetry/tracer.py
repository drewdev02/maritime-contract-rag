import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, Status, StatusCode, Tracer

_logger = logging.getLogger(__name__)
_configured = False


def setup_telemetry(
    service_name: str = "maritime-service",
    otlp_endpoint: str | None = None,
    exporter: str | None = None,
) -> None:
    """Configures the global OpenTelemetry TracerProvider (idempotent).

    ``exporter`` is ``"otlp"`` (OTLP/HTTP to ``otlp_endpoint``), ``"console"`` or ``"none"``.
    When omitted it defaults to ``"otlp"`` if an endpoint is given, otherwise ``"none"``.
    """
    global _configured
    if _configured:
        return

    kind = (exporter or ("otlp" if otlp_endpoint else "none")).lower()
    provider = TracerProvider(resource=Resource.create(attributes={SERVICE_NAME: service_name}))

    if kind == "otlp" and otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        endpoint = otlp_endpoint.rstrip("/")
        if not endpoint.endswith("/v1/traces"):
            endpoint = f"{endpoint}/v1/traces"
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    elif kind == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif kind not in ("none", "otlp"):
        _logger.warning("Unknown OTEL exporter '%s'; tracing export disabled", kind)

    trace.set_tracer_provider(provider)
    _configured = True


def instrument_engine(sync_engine: Any) -> None:
    """Emits one ``db.query`` span per executed statement on a SQLAlchemy engine.

    The official SQLAlchemy instrumentor does not support SQLAlchemy 2.1, so this uses the
    core cursor events. Statement text is recorded without bound parameters (no contract data).
    """
    from sqlalchemy import event

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _start(conn: Any, cursor: Any, statement: str, *_: Any) -> None:
        cm = get_tracer("maritime.db").start_as_current_span(
            "db.query", attributes={"db.system": "postgresql", "db.statement": statement[:200]}
        )
        cm.__enter__()
        conn.info.setdefault("_otel_spans", []).append(cm)

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _end(conn: Any, cursor: Any, statement: str, *_: Any) -> None:
        spans = conn.info.get("_otel_spans")
        if spans:
            spans.pop().__exit__(None, None, None)

    @event.listens_for(sync_engine, "handle_error")
    def _error(context: Any) -> None:
        spans = context.connection.info.get("_otel_spans") if context.connection else None
        if spans:
            spans.pop().__exit__(type(context.original_exception), context.original_exception, None)


def get_tracer(instrumenting_module_name: str) -> Tracer:
    """Retrieves an OpenTelemetry tracer for the given module name."""
    return trace.get_tracer(instrumenting_module_name)


def current_span() -> Span:
    """The span active in this context (a no-op span when there is none)."""
    return trace.get_current_span()


def mark_span_error(target: Span, error_type: str, description: str | None = None) -> None:
    """Flags a span as failed without attaching the exception message.

    Exception messages can echo what was sent to a provider (for example part of a contract), so
    spans carry only the exception *type* and, optionally, a description written by us.
    """
    target.set_attribute("error.type", error_type)
    target.set_status(Status(StatusCode.ERROR, description or error_type))


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span]:
    """Starts a child span with the given attributes (None values are skipped).

    An exception that escapes the block marks the span as an error with its type only (never its
    message). Cancellation is not an error.
    """
    with get_tracer("maritime").start_as_current_span(
        name, record_exception=False, set_status_on_exception=False
    ) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        try:
            yield current
        except (asyncio.CancelledError, GeneratorExit):
            raise
        except BaseException as exc:
            mark_span_error(current, type(exc).__name__)
            raise


def _scrub_url(request_span: Span, request: Any) -> None:
    """Keeps only scheme, host, port and path in the recorded URL.

    Some providers put credentials in the query string (``?key=...``); the default instrumentation
    would copy them into a span.
    """
    url = request.url
    port = f":{url.port}" if url.port else ""
    clean = f"{url.scheme}://{url.host}{port}{url.path}"
    for attribute in ("http.url", "url.full"):
        request_span.set_attribute(attribute, clean)


def instrument_http_clients() -> None:
    """Adds a client span (status, duration) to every ``httpx`` call.

    Pydantic AI and LiteLLM both use ``httpx``, so each request to the LLM and embeddings providers
    shows up under the span that triggered it. Request and response bodies are never recorded.
    """
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument(request_hook=_scrub_url, async_request_hook=_scrub_url)
