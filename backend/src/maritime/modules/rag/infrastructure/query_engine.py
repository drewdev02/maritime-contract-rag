from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from maritime.core.telemetry.logging import get_logger
from maritime.modules.indexing.infrastructure.models import DocumentChunkModel
from maritime.modules.ingestion.domain.value_objects import DocumentStatus
from maritime.modules.ingestion.infrastructure.models import ContractDocumentModel
from maritime.modules.rag.domain.ports import IQueryEngine
from maritime.modules.rag.domain.value_objects import RetrievedChunk

logger = get_logger(__name__)


class PgVectorQueryEngine(IQueryEngine):
    """SQLAlchemy and pgvector implementation for vector similarity retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def retrieve_chunks(
        self,
        query_vector: list[float],
        top_k: int = 5,
        document_id: str | None = None,
    ) -> list[RetrievedChunk]:
        """Performs cosine distance search against indexed contract chunks in pgvector.

        Only chunks belonging to documents in READY status are searched.
        """
        cosine_distance = DocumentChunkModel.embedding.cosine_distance(query_vector).label(
            "distance"
        )

        query = (
            select(
                DocumentChunkModel.id,
                DocumentChunkModel.document_id,
                ContractDocumentModel.filename,
                DocumentChunkModel.page_number,
                DocumentChunkModel.text,
                cosine_distance,
            )
            .join(
                ContractDocumentModel,
                DocumentChunkModel.document_id == ContractDocumentModel.id,
            )
            .where(ContractDocumentModel.status == DocumentStatus.READY)
        )

        if document_id:
            query = query.where(DocumentChunkModel.document_id == document_id)

        query = query.order_by(cosine_distance.asc()).limit(top_k)

        result = await self._session.execute(query)
        rows = result.all()

        chunks: list[RetrievedChunk] = []
        for row in rows:
            dist = float(row.distance) if row.distance is not None else 1.0
            similarity = max(0.0, min(1.0, 1.0 - dist))
            chunks.append(
                RetrievedChunk(
                    chunk_id=str(row.id),
                    document_id=str(row.document_id),
                    document_name=str(row.filename),
                    page_number=int(row.page_number),
                    text=str(row.text),
                    similarity_score=round(similarity, 4),
                )
            )

        logger.info(
            "Retrieved %d candidate chunks via pgvector",
            len(chunks),
            extra={"chunk_count": len(chunks), "top_k": top_k, "document_id": document_id},
        )
        return chunks
