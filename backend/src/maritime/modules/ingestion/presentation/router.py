from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status

from maritime.core.exceptions import EntityNotFoundError, InvariantViolationError
from maritime.infrastructure.di.deps import (
    get_document_file_use_case,
    get_document_status_use_case,
    get_list_documents_use_case,
    get_upload_contract_use_case,
    get_upload_contracts_batch_use_case,
)
from maritime.modules.ingestion.application.dtos import UploadFileDto
from maritime.modules.ingestion.application.use_cases import (
    GetDocumentFileUseCase,
    GetDocumentStatusUseCase,
    ListDocumentsUseCase,
    UploadContractsBatchUseCase,
    UploadContractUseCase,
)
from maritime.modules.ingestion.domain.value_objects import DocumentStatus
from maritime.modules.ingestion.presentation.schemas import (
    BatchUploadItemResponse,
    BatchUploadResponse,
    ContractDocumentListResponse,
    ContractDocumentResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=ContractDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a maritime contract PDF",
)
async def upload_document(
    file: UploadFile,
    use_case: Annotated[UploadContractUseCase, Depends(get_upload_contract_use_case)],
) -> ContractDocumentResponse:
    content = await file.read()
    try:
        doc = await use_case.execute(filename=file.filename or "", content=content)
    except InvariantViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return ContractDocumentResponse(
        document_id=doc.id.value,
        filename=doc.filename,
        status=doc.status.value,
        chunk_count=doc.chunk_count,
        size_bytes=doc.size_bytes,
        error_detail=doc.error_detail,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
    )


@router.post(
    "/upload-batch",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload several maritime contract PDFs in one request",
    description=(
        "Each file is validated and processed independently: a rejected file never blocks "
        "the others. The response lists the outcome of every file in submission order."
    ),
)
async def upload_documents_batch(
    files: list[UploadFile],
    use_case: Annotated[UploadContractsBatchUseCase, Depends(get_upload_contracts_batch_use_case)],
) -> BatchUploadResponse:
    uploads = [
        UploadFileDto(filename=file.filename or "", content=await file.read()) for file in files
    ]
    try:
        result = await use_case.execute(uploads)
    except InvariantViolationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return BatchUploadResponse(
        items=[
            BatchUploadItemResponse(
                filename=item.filename,
                document=(
                    ContractDocumentResponse(**item.document.model_dump())
                    if item.document
                    else None
                ),
                error=item.error,
            )
            for item in result.items
        ],
        accepted=result.accepted,
        rejected=result.rejected,
    )


@router.get(
    "/{document_id}",
    response_model=ContractDocumentResponse,
    summary="Get contract document processing status",
)
async def get_document_status(
    document_id: str,
    use_case: Annotated[GetDocumentStatusUseCase, Depends(get_document_status_use_case)],
) -> ContractDocumentResponse:
    try:
        dto = await use_case.execute(document_id=document_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except InvariantViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return ContractDocumentResponse(
        document_id=dto.document_id,
        filename=dto.filename,
        status=dto.status,
        chunk_count=dto.chunk_count,
        size_bytes=dto.size_bytes,
        error_detail=dto.error_detail,
        created_at=dto.created_at,
    )


@router.get(
    "/{document_id}/file",
    summary="Download the original contract PDF (open with #page=N to jump to a citation)",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def get_document_file(
    document_id: str,
    use_case: Annotated[GetDocumentFileUseCase, Depends(get_document_file_use_case)],
) -> Response:
    try:
        filename, content = await use_case.execute(document_id=document_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except InvariantViolationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    safe_name = filename.replace('"', "")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@router.get(
    "",
    response_model=ContractDocumentListResponse,
    summary="List contract documents",
)
async def list_documents(
    use_case: Annotated[ListDocumentsUseCase, Depends(get_list_documents_use_case)],
    doc_status: Annotated[DocumentStatus | None, Query(alias="status")] = None,
) -> ContractDocumentListResponse:
    dtos = await use_case.execute(status=doc_status)
    items = [
        ContractDocumentResponse(
            document_id=d.document_id,
            filename=d.filename,
            status=d.status,
            chunk_count=d.chunk_count,
            size_bytes=d.size_bytes,
            error_detail=d.error_detail,
            created_at=d.created_at,
        )
        for d in dtos
    ]
    return ContractDocumentListResponse(items=items, total=len(items))
