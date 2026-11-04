import json
import logging
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace

_STANDARD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
    | {"message", "asctime", "taskName"}
)


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON including OpenTelemetry trace context."""

    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span()
        span_context = span.get_span_context() if span else None

        trace_id = (
            format(span_context.trace_id, "032x")
            if span_context and span_context.is_valid
            else None
        )
        span_id = (
            format(span_context.span_id, "016x") if span_context and span_context.is_valid else None
        )

        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id,
            "span_id": span_id,
        }

        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key not in log_data:
                log_data[key] = value

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Configures root logger with structured JSON formatting."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Replace existing handlers to prevent duplicate output
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Returns a logger instance with the specified name."""
    return logging.getLogger(name)
