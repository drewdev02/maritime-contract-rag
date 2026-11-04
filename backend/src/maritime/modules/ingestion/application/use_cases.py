import hashlib

from maritime.core.events.event_bus import IEventBus
from maritime.core.exceptions import ConflictError, EntityNotFoundError, InvariantViolationError
from maritime.modules.ingestion.application.dtos import (
    BatchUploadItemDto,
    BatchUploadResultDto,
    DocumentStatusDto,
    DocumentSummaryDto,
    UploadFileDto,
)
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.ports import IDocumentRepository, IFileStorage
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)


class UploadContractUseCase:
    """Use case to upload a new maritime contract document with SHA-256 idempotency check."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        file_storage: IFileStorage,
        event_bus: IEventBus,
        max_file_size_bytes: int,
    ) -> None:
        self._document_repo = document_repository
        self._file_storage = file_storage
        self._event_bus = event_bus
        self._max_file_size_bytes = max_file_size_bytes

    async def execute(self, filename: str, content: bytes) -> ContractDocument:
        """Executes contract document upload.

        Validates payload, enforces idempotency by SHA-256 hash, persists file and aggregate,
        and dispatches domain events.
        """
        if not filename or not filename.strip():
            raise InvariantViolationError("Filename is required.")

        if not content:
            raise InvariantViolationError("File content cannot be empty.")

        if len(content) > self._max_file_size_bytes:
            raise InvariantViolationError(
                f"File size exceeds maximum allowed limit of {self._max_file_size_bytes} bytes."
            )

        if not filename.lower().endswith(".pdf"):
            raise InvariantViolationError("Only PDF files are supported.")

        if not content.startswith(b"%PDF-"):
            raise InvariantViolationError("File content is not a valid PDF document.")

        raw_hash = hashlib.sha256(content).hexdigest()
        content_hash = ContentHash(raw_hash)

        # Idempotency check: Return existing document if already present
        existing_doc = await self._document_repo.find_by_content_hash(content_hash)
        if existing_doc:
            return await self._reuse_existing(existing_doc)

        doc_id = DocumentId.generate()
        await self._file_storage.save(
            doc_id=doc_id.value,
            filename=filename,
            content=content,
        )

        document = ContractDocument.create(
            id=doc_id,
            filename=filename,
            content_hash=content_hash,
            size_bytes=len(content),
        )

        try:
            await self._document_repo.save(document)
        except ConflictError:
            # A concurrent upload of the same bytes won the race on the unique hash index.
            winner = await self._document_repo.find_by_content_hash(content_hash)
            if winner is None:
                raise
            return await self._reuse_existing(winner)
        await self._event_bus.publish_all(document.pull_events())

        return document

    async def _reuse_existing(self, document: ContractDocument) -> ContractDocument:
        """Returns the existing document; a previously FAILED one is queued again."""
        if document.status == DocumentStatus.FAILED:
            document.request_retry()
            await self._document_repo.save(document)
            await self._event_bus.publish_all(document.pull_events())
        return document


class UploadContractsBatchUseCase:
    """Use case to upload several contracts, each validated and stored independently.

    A rejected file never blocks the others; the result lists every file's outcome in
    submission order.
    """

    def __init__(self, upload_contract: UploadContractUseCase) -> None:
        self._upload_contract = upload_contract

    async def execute(self, files: list[UploadFileDto]) -> BatchUploadResultDto:
        if not files:
            raise InvariantViolationError("At least one file is required.")

        items: list[BatchUploadItemDto] = []
        for file in files:
            try:
                doc = await self._upload_contract.execute(
                    filename=file.filename, content=file.content
                )
            except InvariantViolationError as e:
                items.append(BatchUploadItemDto(filename=file.filename, error=str(e)))
                continue
            items.append(
                BatchUploadItemDto(
                    filename=file.filename,
                    document=DocumentStatusDto(
                        document_id=doc.id.value,
                        filename=doc.filename,
                        status=doc.status.value,
                        chunk_count=doc.chunk_count,
                        size_bytes=doc.size_bytes,
                        error_detail=doc.error_detail,
                        created_at=doc.created_at.isoformat() if doc.created_at else None,
                    ),
                )
            )

        accepted = sum(1 for item in items if item.document is not None)
        return BatchUploadResultDto(items=items, accepted=accepted, rejected=len(items) - accepted)


class GetDocumentStatusUseCase:
    """Use case to retrieve the current processing status of a contract document."""

    def __init__(self, document_repository: IDocumentRepository) -> None:
        self._document_repo = document_repository

    async def execute(self, document_id: str) -> DocumentStatusDto:
        doc_id = DocumentId.from_str(document_id)
        doc = await self._document_repo.find_by_id(doc_id)
        if not doc:
            raise EntityNotFoundError(
                entity_name="ContractDocument",
                entity_id=document_id,
            )

        return DocumentStatusDto(
            document_id=doc.id.value,
            filename=doc.filename,
            status=doc.status.value,
            chunk_count=doc.chunk_count,
            size_bytes=doc.size_bytes,
            error_detail=doc.error_detail,
            created_at=doc.created_at.isoformat() if doc.created_at else None,
        )


class GetDocumentFileUseCase:
    """Use case to read the original PDF of a contract so a citation can open it."""

    def __init__(
        self, document_repository: IDocumentRepository, file_storage: IFileStorage
    ) -> None:
        self._document_repo = document_repository
        self._file_storage = file_storage

    async def execute(self, document_id: str) -> tuple[str, bytes]:
        doc = await self._document_repo.find_by_id(DocumentId.from_str(document_id))
        if not doc:
            raise EntityNotFoundError(entity_name="ContractDocument", entity_id=document_id)

        path = f"{document_id}/{doc.filename}"
        if not await self._file_storage.exists(path):
            raise EntityNotFoundError(entity_name="ContractDocumentFile", entity_id=document_id)
        return doc.filename, await self._file_storage.read(path)


class ListDocumentsUseCase:
    """Use case to list all contract documents, optionally filtered by status."""

    def __init__(self, document_repository: IDocumentRepository) -> None:
        self._document_repo = document_repository

    async def execute(self, status: DocumentStatus | None = None) -> list[DocumentSummaryDto]:
        documents = await self._document_repo.list_all(status=status)
        return [
            DocumentSummaryDto(
                document_id=doc.id.value,
                filename=doc.filename,
                status=doc.status.value,
                chunk_count=doc.chunk_count,
                size_bytes=doc.size_bytes,
                error_detail=doc.error_detail,
                created_at=doc.created_at.isoformat() if doc.created_at else None,
            )
            for doc in documents
        ]
