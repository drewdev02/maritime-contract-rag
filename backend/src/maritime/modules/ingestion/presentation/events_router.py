import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from maritime.core.telemetry.logging import get_logger
from maritime.infrastructure.events.hub import (
    BroadcastItem,
    EventHub,
    is_stream_id,
    stream_id_key,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

HEARTBEAT_SECONDS = 15.0
RECONNECT_MILLIS = 3000


def format_sse(item: BroadcastItem) -> str:
    """One Server-Sent Event. ``id`` is the stream id, so the browser resumes with Last-Event-ID."""
    envelope = item.envelope
    data = {
        "type": envelope.type,
        "event_id": envelope.event_id,
        "occurred_at": envelope.occurred_at,
        **envelope.payload,
    }
    return (
        f"id: {item.stream_id}\n"
        f"event: {envelope.type}\n"
        f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    )


async def document_event_stream(
    hub: EventHub,
    last_event_id: str | None,
    heartbeat_seconds: float = HEARTBEAT_SECONDS,
) -> AsyncGenerator[str, None]:
    """Replays what a reconnecting client missed, then streams live events.

    The client is subscribed *before* the replay is read, so an event that arrives in between is
    queued and not lost; ids already sent are skipped so nothing is delivered twice.
    """
    with hub.broadcaster.subscribe() as subscription:
        yield f"retry: {RECONNECT_MILLIS}\n\n"

        last_sent: str | None = None
        if last_event_id and is_stream_id(last_event_id):
            for entry in await hub.replay(last_event_id):
                if entry.envelope is not None:
                    yield format_sse(BroadcastItem(entry.stream_id, entry.envelope))
                last_sent = entry.stream_id

        while True:
            try:
                item = await asyncio.wait_for(subscription.queue.get(), heartbeat_seconds)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if item is None:
                # Dropped (too slow, or the server is shutting down): the client reconnects.
                return
            if last_sent is not None and stream_id_key(item.stream_id) <= stream_id_key(last_sent):
                continue
            last_sent = item.stream_id
            yield format_sse(item)


@router.get(
    "/events",
    summary="Live document events (Server-Sent Events)",
    description=(
        "Streams `document.uploaded`, `document.processing_started`, `document.ready` and "
        "`document.failed` as they happen. Reconnecting with `Last-Event-ID` replays what was "
        "missed. Clients should keep polling `GET /documents` as a fallback."
    ),
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_document_events(
    request: Request,
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    hub: EventHub | None = getattr(request.app.state, "event_hub", None)
    if hub is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El flujo de eventos no está habilitado. Consulta el listado de documentos.",
        )
    return StreamingResponse(
        document_event_stream(hub, last_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
