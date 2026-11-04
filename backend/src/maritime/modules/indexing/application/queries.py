from maritime.core.exceptions import EntityNotFoundError
from maritime.modules.indexing.domain.entities import DocumentChunk
from maritime.modules.indexing.domain.ports import IChunkRepository
from maritime.modules.ingestion.domain.value_objects import DocumentId


class GetChunkUseCase:
    """Returns one indexed fragment so a citation can be traced back to its original text."""

    def __init__(self, chunk_repository: IChunkRepository) -> None:
        self._chunk_repo = chunk_repository

    async def execute(self, document_id: str, chunk_id: str) -> DocumentChunk:
        chunks = await self._chunk_repo.find_by_document_id(DocumentId.from_str(document_id))
        for chunk in chunks:
            if chunk.id.value == chunk_id:
                return chunk
        raise EntityNotFoundError(entity_name="DocumentChunk", entity_id=chunk_id)
