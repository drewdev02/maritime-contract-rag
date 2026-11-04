import os

# Tests must never export traces, even when a developer's .env enables an OTLP collector.
os.environ["OTEL_TRACES_EXPORTER"] = "none"
