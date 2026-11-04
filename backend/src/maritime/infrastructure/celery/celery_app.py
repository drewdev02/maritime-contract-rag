from celery import Celery
from celery.signals import worker_init, worker_process_init
from opentelemetry.instrumentation.celery import CeleryInstrumentor

from maritime.core.telemetry.logging import configure_logging
from maritime.core.telemetry.tracer import instrument_http_clients, setup_telemetry
from maritime.infrastructure.config import settings

celery_app = Celery(
    "maritime_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Delivery guarantees: acknowledge a message only after the task finished, so a worker that
    # is killed mid-task (SIGKILL/OOM) gets its message redelivered. The task is idempotent.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Redis redelivers unacked messages after this timeout; it must exceed the longest task.
    broker_transport_options={"visibility_timeout": settings.TASK_VISIBILITY_TIMEOUT_SECONDS},
    # Backstop for documents that remain in PROCESSING (needs a `celery beat` process).
    beat_schedule={
        "fail-stuck-documents": {
            "task": "maritime.fail_stuck_documents",
            "schedule": 60.0,
        },
    },
)


def _init_worker_telemetry() -> None:
    configure_logging()
    setup_telemetry(
        service_name=settings.OTEL_SERVICE_NAME,
        otlp_endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        exporter=settings.OTEL_TRACES_EXPORTER,
    )
    instrument_http_clients()  # the worker calls the embeddings provider over httpx too


@worker_process_init.connect  # type: ignore[untyped-decorator]
def _on_worker_process_init(**_: object) -> None:
    """Prefork pool: configure tracing inside every child (exporter threads don't survive fork)."""
    _init_worker_telemetry()


@worker_init.connect  # type: ignore[untyped-decorator]
def _on_worker_init(sender: object = None, **_: object) -> None:
    """Non-forking pools (solo/threads): configure tracing in the main process."""
    if "prefork" not in str(getattr(sender, "pool_cls", "")):
        _init_worker_telemetry()


# Producer side (API process): propagates the trace context in the task headers on .delay().
CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]

# Import task definitions to ensure registration
import maritime.modules.indexing.tasks.celery_tasks  # noqa: E402, F401


@celery_app.task(name="maritime.ping")  # type: ignore[untyped-decorator]
def ping_task() -> str:
    """Smoke task to verify Celery worker connectivity."""
    return "pong"
