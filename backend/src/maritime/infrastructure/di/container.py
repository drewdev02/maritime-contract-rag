from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from maritime.core.events.event_bus import IEventBus
from maritime.infrastructure.config import Settings
from maritime.modules.indexing.application.queries import GetChunkUseCase
from maritime.modules.indexing.application.use_cases import IndexDocumentUseCase
from maritime.modules.indexing.domain.ports import IEmbeddingService
from maritime.modules.indexing.infrastructure.embeddings.litellm_embedding import (
    LiteLlmEmbeddingAdapter,
)
from maritime.modules.indexing.infrastructure.embeddings.mock_embedding import (
    MockDeterministicEmbeddingAdapter,
)
from maritime.modules.indexing.infrastructure.parsers.pdfplumber_parser import PdfplumberParser
from maritime.modules.indexing.infrastructure.repository import SqlAlchemyChunkRepository
from maritime.modules.indexing.infrastructure.services.markdown_table_chunker import (
    MarkdownTableChunker,
)
from maritime.modules.ingestion.application.use_cases import (
    GetDocumentFileUseCase,
    GetDocumentStatusUseCase,
    ListDocumentsUseCase,
    UploadContractsBatchUseCase,
    UploadContractUseCase,
)
from maritime.modules.ingestion.infrastructure.repository import SqlAlchemyDocumentRepository
from maritime.modules.ingestion.infrastructure.storage import LocalFileStorageAdapter
from maritime.modules.rag.application.use_cases import AskContractQuestionUseCase
from maritime.modules.rag.domain.ports import ILlmService
from maritime.modules.rag.domain.services import StrictCitationValidator
from maritime.modules.rag.infrastructure.llm.mock_llm import MockDeterministicLlmAdapter
from maritime.modules.rag.infrastructure.llm.pydantic_ai_adapter import PydanticAiLlmAdapter
from maritime.modules.rag.infrastructure.query_engine import PgVectorQueryEngine


class ApplicationContainer:
    """Composition Root: Assembles dependencies and builds use cases."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: IEventBus,
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.event_bus = event_bus
        self.settings = settings
        self.file_storage = LocalFileStorageAdapter(base_path=settings.STORAGE_PATH)
        self.pdf_parser = PdfplumberParser()
        self.chunking_service = MarkdownTableChunker(
            max_chunk_chars=settings.CHUNK_MAX_CHARS,
            overlap_chars=settings.CHUNK_OVERLAP_CHARS,
        )
        self.embedding_service = self._create_embedding_service()
        self.citation_validator = StrictCitationValidator()

    def _create_embedding_service(self) -> IEmbeddingService:
        provider = (self.settings.EMBEDDING_PROVIDER or self.settings.LLM_PROVIDER).lower()
        if provider in ("gemini", "openai") and (
            self.settings.EMBEDDING_API_KEY or self.settings.EMBEDDING_BASE_URL
        ):
            return LiteLlmEmbeddingAdapter(
                api_key=self.settings.EMBEDDING_API_KEY,
                model=self.settings.EMBEDDING_MODEL,
                base_url=self.settings.EMBEDDING_BASE_URL,
                dimensions=self.settings.EMBEDDING_DIMENSIONS,
                timeout=self.settings.EMBEDDING_TIMEOUT,
                max_retries=self.settings.EMBEDDING_MAX_RETRIES,
            )
        return MockDeterministicEmbeddingAdapter()

    def _create_llm_service(self) -> ILlmService:
        provider = self.settings.LLM_PROVIDER.lower()
        if provider in ("gemini", "openai") and (
            self.settings.LLM_API_KEY or self.settings.LLM_BASE_URL
        ):
            return PydanticAiLlmAdapter(
                api_key=self.settings.LLM_API_KEY,
                provider=provider,
                model_name=self.settings.LLM_MODEL,
                base_url=self.settings.LLM_BASE_URL,
                timeout=self.settings.LLM_TIMEOUT,
            )
        return MockDeterministicLlmAdapter()

    def get_upload_contract_use_case(self, session: AsyncSession) -> UploadContractUseCase:
        repo = SqlAlchemyDocumentRepository(session=session)
        return UploadContractUseCase(
            document_repository=repo,
            file_storage=self.file_storage,
            event_bus=self.event_bus,
            max_file_size_bytes=self.settings.MAX_FILE_SIZE_BYTES,
        )

    def get_upload_contracts_batch_use_case(
        self, session: AsyncSession
    ) -> UploadContractsBatchUseCase:
        return UploadContractsBatchUseCase(
            upload_contract=self.get_upload_contract_use_case(session=session)
        )

    def get_document_status_use_case(self, session: AsyncSession) -> GetDocumentStatusUseCase:
        repo = SqlAlchemyDocumentRepository(session=session)
        return GetDocumentStatusUseCase(document_repository=repo)

    def get_list_documents_use_case(self, session: AsyncSession) -> ListDocumentsUseCase:
        repo = SqlAlchemyDocumentRepository(session=session)
        return ListDocumentsUseCase(document_repository=repo)

    def get_document_file_use_case(self, session: AsyncSession) -> GetDocumentFileUseCase:
        repo = SqlAlchemyDocumentRepository(session=session)
        return GetDocumentFileUseCase(document_repository=repo, file_storage=self.file_storage)

    def get_chunk_use_case(self, session: AsyncSession) -> GetChunkUseCase:
        return GetChunkUseCase(chunk_repository=SqlAlchemyChunkRepository(session=session))

    def get_index_document_use_case(self, session: AsyncSession) -> IndexDocumentUseCase:
        doc_repo = SqlAlchemyDocumentRepository(session=session)
        chunk_repo = SqlAlchemyChunkRepository(session=session)
        return IndexDocumentUseCase(
            document_repository=doc_repo,
            chunk_repository=chunk_repo,
            file_storage=self.file_storage,
            pdf_parser=self.pdf_parser,
            chunking_service=self.chunking_service,
            embedding_service=self.embedding_service,
            event_bus=self.event_bus,
        )

    def get_ask_contract_question_use_case(
        self, session: AsyncSession
    ) -> AskContractQuestionUseCase:
        query_engine = PgVectorQueryEngine(session=session)
        llm_service = self._create_llm_service()
        return AskContractQuestionUseCase(
            query_engine=query_engine,
            llm_service=llm_service,
            embedding_service=self.embedding_service,
            citation_validator=self.citation_validator,
            similarity_threshold=self.settings.RAG_SIMILARITY_THRESHOLD,
        )
