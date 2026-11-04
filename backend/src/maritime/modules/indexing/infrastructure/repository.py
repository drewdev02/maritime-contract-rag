from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from maritime.modules.indexing.domain.entities import DocumentChunk
from maritime.modules.indexing.domain.ports import IChunkRepository
from maritime.modules.indexing.domain.value_objects import ChunkId, PageNumber, TextSpan
from maritime.modules.indexing.infrastructure.models import DocumentChunkModel
from maritime.modules.ingestion.domain.value_objects import DocumentId


class SqlAlchemyChunkRepository(IChunkRepository):
    """SQLAlchemy implementation of IChunkRepository with pgvector cosine distance search."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_chunks(self, chunks: Sequence[DocumentChunk]) -> None:
        models = [
            DocumentChunkModel(
                id=c.id.value,
                document_id=c.document_id.value,
                chunk_index=c.chunk_index,
                page_number=c.page_number.value,
                start_char_idx=c.span.start_char,
                end_char_idx=c.span.end_char,
                text=c.text,
                embedding=c.embedding,
            )
            for c in chunks
        ]
        self._session.add_all(models)
        await self._session.flush()

    async def delete_by_document_id(self, document_id: DocumentId) -> None:
        stmt = delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id.value)
        await self._session.execute(stmt)
        await self._session.flush()

    async def find_by_document_id(self, document_id: DocumentId) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id.value)
            .order_by(DocumentChunkModel.chunk_index.asc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        document_id: DocumentId | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        # pgvector cosine_distance returns value between 0.0 (identical) and 2.0 (opposite)
        distance_col = DocumentChunkModel.embedding.cosine_distance(query_embedding).label(
            "distance"
        )

        stmt = select(DocumentChunkModel, distance_col)
        if document_id is not None:
            stmt = stmt.where(DocumentChunkModel.document_id == document_id.value)

        stmt = stmt.order_by(distance_col.asc()).limit(top_k)

        result = await self._session.execute(stmt)
        rows = result.all()

        results: list[tuple[DocumentChunk, float]] = []
        for model, dist in rows:
            similarity = max(0.0, 1.0 - float(dist))
            results.append((self._to_domain(model), similarity))

        return results

    @staticmethod
    def _to_domain(model: DocumentChunkModel) -> DocumentChunk:
        embedding_val = [float(x) for x in model.embedding] if model.embedding is not None else None
        return DocumentChunk(
            id=ChunkId.from_str(model.id),
            document_id=DocumentId.from_str(model.document_id),
            chunk_index=model.chunk_index,
            page_number=PageNumber(model.page_number),
            text=model.text,
            span=TextSpan(start_char=model.start_char_idx, end_char=model.end_char_idx),
            embedding=embedding_val,
        )
