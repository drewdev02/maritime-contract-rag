from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from maritime.core.exceptions import EntityNotFoundError, InvariantViolationError
from maritime.infrastructure.di.deps import get_chunk_use_case
from maritime.modules.indexing.application.queries import GetChunkUseCase

router = APIRouter(prefix="/documents", tags=["documents"])


class ChunkResponse(BaseModel):
    """An indexed fragment with the location it was extracted from."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    document_id: str
    chunk_index: int
    page_number: int
    start_char: int
    end_char: int
    text: str


@router.get(
    "/{document_id}/chunks/{chunk_id}",
    response_model=ChunkResponse,
    summary="Get the original text fragment behind a citation",
)
async def get_chunk(
    document_id: str,
    chunk_id: str,
    use_case: Annotated[GetChunkUseCase, Depends(get_chunk_use_case)],
) -> ChunkResponse:
    try:
        chunk = await use_case.execute(document_id=document_id, chunk_id=chunk_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except InvariantViolationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return ChunkResponse(
        chunk_id=chunk.id.value,
        document_id=chunk.document_id.value,
        chunk_index=chunk.chunk_index,
        page_number=chunk.page_number.value,
        start_char=chunk.span.start_char,
        end_char=chunk.span.end_char,
        text=chunk.text,
    )
