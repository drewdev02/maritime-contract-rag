from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from maritime.modules.rag.domain.value_objects import (
    RagResponse,
    RetrievedChunk,
    StreamChunk,
)


class IQueryEngine(ABC):
    """Port for retrieving semantically relevant contract chunks from the vector database."""

    @abstractmethod
    async def retrieve_chunks(
        self,
        query_vector: list[float],
        top_k: int = 5,
        document_id: str | None = None,
    ) -> list[RetrievedChunk]:
        """Retrieves top_k chunks matching query_vector from ready contract documents."""
        pass


class ILlmService(ABC):
    """Port for generating structured answers with verifiable contract citations."""

    @abstractmethod
    async def generate_answer(
        self,
        query: str,
        context_chunks: list[RetrievedChunk],
    ) -> RagResponse:
        """Generates a structured RagResponse given the user query and retrieved context chunks."""
        pass

    @abstractmethod
    def generate_answer_stream(
        self,
        query: str,
        context_chunks: list[RetrievedChunk],
    ) -> AsyncIterator[StreamChunk]:
        """Streams text deltas incrementally followed by the final metadata chunk."""
        pass
