import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from maritime.core.exceptions import ProviderError
from maritime.core.telemetry.logging import get_logger
from maritime.infrastructure.di.deps import get_ask_contract_question_use_case
from maritime.modules.rag.application.use_cases import AskContractQuestionUseCase
from maritime.modules.rag.domain.value_objects import StreamDeltaChunk, StreamMetaChunk
from maritime.modules.rag.presentation.schemas import (
    CitationResponse,
    QueryRequest,
    QueryResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/query", tags=["RAG Assistant"])


@router.post(
    "",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query maritime contracts with strict citations",
    description=(
        "Retrieves relevant contract fragments via pgvector and synthesizes an answer "
        "accompanied by strict, verifiable citations or an explicit abstention response."
    ),
)
async def query_contracts(
    payload: QueryRequest,
    use_case: Annotated[AskContractQuestionUseCase, Depends(get_ask_contract_question_use_case)],
) -> QueryResponse:
    try:
        domain_response = await use_case.execute(
            query=payload.query,
            top_k=payload.top_k,
            document_id=payload.document_id,
        )
    except ProviderError as exc:
        logger.error("AI provider failure during query", extra={"provider_error_kind": exc.kind})
        raise HTTPException(status_code=exc.http_status, detail=exc.user_message) from exc

    citations = [
        CitationResponse(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            document_name=c.document_name,
            page_number=c.page_number,
            snippet_text=c.snippet_text,
        )
        for c in domain_response.citations
    ]

    return QueryResponse(
        answer=domain_response.answer,
        citations=citations,
        has_sufficient_evidence=domain_response.has_sufficient_evidence,
        confidence_score=domain_response.confidence_score,
    )


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
    summary="Query maritime contracts with streaming tokens and verified citations",
    description=(
        "Streams the natural language answer using Server-Sent Events (SSE), "
        "followed by verified citations or an explicit abstention notice."
    ),
)
async def query_contracts_stream(
    payload: QueryRequest,
    use_case: Annotated[AskContractQuestionUseCase, Depends(get_ask_contract_question_use_case)],
) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in use_case.execute_stream(
                query=payload.query,
                top_k=payload.top_k,
                document_id=payload.document_id,
            ):
                if isinstance(chunk, StreamDeltaChunk):
                    payload_data = json.dumps({"delta": chunk.delta}, ensure_ascii=False)
                    yield f"event: token\ndata: {payload_data}\n\n"
                elif isinstance(chunk, StreamMetaChunk):
                    citations_data = [
                        {
                            "chunk_id": c.chunk_id,
                            "document_id": c.document_id,
                            "document_name": c.document_name,
                            "page_number": c.page_number,
                            "snippet_text": c.snippet_text,
                        }
                        for c in chunk.citations
                    ]
                    meta_payload = json.dumps(
                        {
                            "citations": citations_data,
                            "has_sufficient_evidence": chunk.has_sufficient_evidence,
                            "confidence_score": chunk.confidence_score,
                        },
                        ensure_ascii=False,
                    )
                    yield f"event: meta\ndata: {meta_payload}\n\n"
            yield "event: done\ndata: {}\n\n"
        except ProviderError as exc:
            logger.error(
                "AI provider failure during streaming", extra={"provider_error_kind": exc.kind}
            )
            err_payload = json.dumps(
                {"error": exc.user_message, "kind": exc.kind, "status": exc.http_status},
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {err_payload}\n\n"
        except Exception:
            logger.error("Error occurred during query streaming", exc_info=True)
            err_payload = json.dumps(
                {"error": "No se pudo completar la consulta. Intenta nuevamente."},
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {err_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
