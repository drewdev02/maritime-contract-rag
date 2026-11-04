from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from maritime.core.telemetry.logging import configure_logging
from maritime.core.telemetry.tracer import instrument_http_clients, setup_telemetry
from maritime.infrastructure.config import settings
from maritime.infrastructure.di.deps import build_event_hub
from maritime.modules.indexing.presentation.router import router as chunks_router
from maritime.modules.ingestion.presentation.events_router import router as events_router
from maritime.modules.ingestion.presentation.router import router as ingestion_router
from maritime.modules.rag.presentation.router import router as rag_router

setup_telemetry(
    service_name=settings.OTEL_SERVICE_NAME,
    otlp_endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
    exporter=settings.OTEL_TRACES_EXPORTER,
)
instrument_http_clients()  # spans for every call to the LLM / embeddings providers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()  # structured JSON logs with trace_id, installed at server start
    hub = build_event_hub()
    if hub is not None:
        await hub.start()
        app.state.event_hub = hub
    try:
        yield
    finally:
        if hub is not None:
            await hub.stop()
        app.state.event_hub = None


app = FastAPI(
    lifespan=lifespan,
    title="Naviera Portecho - Maritime Contract RAG API",
    version="0.1.0",
    description="API interna para gestión e ingesta de contratos marítimos y consultas RAG con citas.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health checks and the long-lived SSE connection would only add noise (or one endless span).
FastAPIInstrumentor.instrument_app(app, excluded_urls="health,documents/events")

# Include module routers under /api/v1. The events router must come first: `/documents/events`
# would otherwise be captured by `/documents/{document_id}`.
app.include_router(events_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(chunks_router, prefix="/api/v1")
app.include_router(rag_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "maritime-api"}


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    return {
        "service": "Naviera Portecho RAG API",
        "docs": "/docs",
        "health": "/health",
    }
