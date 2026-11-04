from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from maritime.core.exceptions import ConflictError
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.ports import IDocumentRepository
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)
from maritime.modules.ingestion.infrastructure.models import ContractDocumentModel


class SqlAlchemyDocumentRepository(IDocumentRepository):
    """SQLAlchemy implementation of IDocumentRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, document: ContractDocument) -> None:
        existing = await self._session.get(ContractDocumentModel, document.id.value)
        if existing:
            existing.filename = document.filename
            existing.content_hash = document.content_hash.value
            existing.size_bytes = document.size_bytes
            existing.status = document.status.value
            existing.chunk_count = document.chunk_count
            existing.error_detail = document.error_detail
        else:
            model = ContractDocumentModel(
                id=document.id.value,
                filename=document.filename,
                content_hash=document.content_hash.value,
                size_bytes=document.size_bytes,
                status=document.status.value,
                chunk_count=document.chunk_count,
                error_detail=document.error_detail,
            )
            try:
                # SAVEPOINT: a unique-hash violation must not poison the caller's transaction.
                async with self._session.begin_nested():
                    self._session.add(model)
                    await self._session.flush()
            except IntegrityError as exc:
                raise ConflictError(
                    "A document with the same content hash already exists."
                ) from exc
            return
        await self._session.flush()

    async def find_by_id(self, document_id: DocumentId) -> ContractDocument | None:
        model = await self._session.get(ContractDocumentModel, document_id.value)
        if not model:
            return None
        return self._to_domain(model)

    async def find_by_content_hash(self, content_hash: ContentHash) -> ContractDocument | None:
        stmt = select(ContractDocumentModel).where(
            ContractDocumentModel.content_hash == content_hash.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def list_all(self, status: DocumentStatus | None = None) -> list[ContractDocument]:
        stmt = select(ContractDocumentModel)
        if status is not None:
            stmt = stmt.where(ContractDocumentModel.status == status.value)
        stmt = stmt.order_by(ContractDocumentModel.created_at.desc())
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def fail_stuck_processing(self, older_than: datetime, reason: str) -> list[str]:
        """Marks documents stuck in PROCESSING since before ``older_than`` as FAILED.

        Backstop for workers that die without running any error handler (e.g. SIGKILL/OOM).
        Returns the ids that were failed.
        """
        stmt = (
            update(ContractDocumentModel)
            .where(
                ContractDocumentModel.status == DocumentStatus.PROCESSING.value,
                ContractDocumentModel.updated_at < older_than,
            )
            .values(status=DocumentStatus.FAILED.value, error_detail=reason)
            .returning(ContractDocumentModel.id)
        )
        result = await self._session.execute(stmt)
        return [str(row[0]) for row in result.all()]

    @staticmethod
    def _to_domain(model: ContractDocumentModel) -> ContractDocument:
        return ContractDocument(
            id=DocumentId.from_str(model.id),
            filename=model.filename,
            content_hash=ContentHash(model.content_hash),
            size_bytes=model.size_bytes,
            status=DocumentStatus(model.status),
            chunk_count=model.chunk_count,
            error_detail=model.error_detail,
            created_at=model.created_at,
        )
