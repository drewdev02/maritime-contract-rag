from maritime.core.events.event_bus import IEventBus
from maritime.core.exceptions import (
    DomainError,
    EmptyDocumentChunksError,
    EntityNotFoundError,
    ProviderError,
)
from maritime.core.telemetry.logging import get_logger
from maritime.core.telemetry.tracer import current_span, mark_span_error, span
from maritime.modules.indexing.domain.ports import (
    IChunkingService,
    IChunkRepository,
    IEmbeddingService,
    IPdfParser,
)
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.ports import IDocumentRepository, IFileStorage
from maritime.modules.ingestion.domain.value_objects import DocumentId, DocumentStatus

logger = get_logger(__name__)


class IndexDocumentUseCase:
    """Use case to parse, chunk, embed, and index a maritime contract into pgvector."""

    def __init__(
        self,
        document_repository: IDocumentRepository,
        chunk_repository: IChunkRepository,
        file_storage: IFileStorage,
        pdf_parser: IPdfParser,
        chunking_service: IChunkingService,
        embedding_service: IEmbeddingService,
        event_bus: IEventBus,
    ) -> None:
        self._doc_repo = document_repository
        self._chunk_repo = chunk_repository
        self._file_storage = file_storage
        self._pdf_parser = pdf_parser
        self._chunking_service = chunking_service
        self._embedding_service = embedding_service
        self._event_bus = event_bus

    async def execute(self, document_id: str) -> None:
        """Runs the whole pipeline. Callers that want ``processing`` to be visible while the
        work runs commit between ``start`` and ``run`` (see the Celery task)."""
        if await self.start(document_id):
            await self.run(document_id)

    async def start(self, document_id: str) -> bool:
        """Marks the document as PROCESSING and publishes the event.

        Returns False when there is nothing to do: Celery delivers at-least-once, and a document
        that is already indexed must be a no-op so a redelivered task can never duplicate or wipe
        its chunks.
        """
        doc = await self._load(document_id)
        if doc.status == DocumentStatus.READY:
            logger.info(
                "Document already indexed; skipping duplicate processing",
                extra={"document_id": document_id},
            )
            return False

        doc.mark_as_processing()
        await self._doc_repo.save(doc)
        await self._event_bus.publish_all(doc.pull_events())
        return True

    async def run(self, document_id: str) -> None:
        with span("index.document", document_id=document_id):
            await self._run(document_id)

    async def _load(self, document_id: str) -> ContractDocument:
        doc = await self._doc_repo.find_by_id(DocumentId.from_str(document_id))
        if not doc:
            raise EntityNotFoundError(entity_name="ContractDocument", entity_id=document_id)
        return doc

    async def _run(self, document_id: str) -> None:
        doc_id = DocumentId.from_str(document_id)
        doc = await self._load(document_id)

        try:
            # 1. Retrieve physical PDF bytes from storage
            # In LocalFileStorageAdapter, files are stored under base_path / doc_id / filename
            # Check candidate storage paths
            candidate_paths = [
                f"{document_id}/{doc.filename}",
                f"storage/contracts/{document_id}/{doc.filename}",
                f"{document_id}.pdf",
                doc.filename,
            ]
            pdf_bytes: bytes | None = None
            for p in candidate_paths:
                if await self._file_storage.exists(p):
                    pdf_bytes = await self._file_storage.read(p)
                    break

            if pdf_bytes is None:
                # Direct attempt with default relative path
                pdf_bytes = await self._file_storage.read(f"{document_id}/{doc.filename}")

            # 2. Parse structural text and tables with pdfplumber
            with span("index.parse", document_id=document_id, size_bytes=len(pdf_bytes)) as sp:
                pages = self._pdf_parser.parse(pdf_bytes)
                sp.set_attribute("index.pages", len(pages))

            # 3. Chunk pages preserving Markdown tables and character spans
            with span("index.chunk", document_id=document_id) as sp:
                chunks = self._chunking_service.chunk(pages, document_id=doc_id)
                sp.set_attribute("index.chunk_count", len(chunks))
            if not chunks:
                raise EmptyDocumentChunksError()

            # 4. Generate vector embeddings for all chunks
            texts = [c.text for c in chunks]
            with span("index.embed", document_id=document_id, **{"index.chunk_count": len(texts)}):
                embeddings = self._embedding_service.embed_batch(texts)
            for chunk, emb in zip(chunks, embeddings, strict=True):
                chunk.attach_embedding(emb)

            # 5. Atomic persistence: clean any partial/stale chunks and insert new ones
            with span(
                "index.persist", document_id=document_id, **{"index.chunk_count": len(chunks)}
            ):
                await self._chunk_repo.delete_by_document_id(doc_id)
                await self._chunk_repo.save_chunks(chunks)

            # 6. Mark document as READY with indexed chunk count
            doc.mark_as_ready(total_chunks=len(chunks))
            await self._doc_repo.save(doc)
            await self._event_bus.publish_all(doc.pull_events())

            logger.info(
                "Document indexed successfully for document_id=%s (chunks=%d)",
                document_id,
                len(chunks),
                extra={"document_id": document_id, "chunk_count": len(chunks)},
            )

        except Exception as e:
            # Atomic rollback: guarantee no orphaned chunks remain in pgvector
            await self._chunk_repo.delete_by_document_id(doc_id)

            if isinstance(e, ProviderError):
                reason = e.user_message
            elif isinstance(e, DomainError):
                reason = str(e)
            else:
                reason = "Error al procesar el archivo PDF"
            doc.mark_as_failed(reason=reason)
            await self._doc_repo.save(doc)
            await self._event_bus.publish_all(doc.pull_events())

            # The failure is handled (the document ends FAILED), so the exception never reaches the
            # span on its own: flag it, with the type and the readable reason only.
            failed_span = current_span()
            mark_span_error(failed_span, type(e).__name__, reason)
            failed_span.set_attribute("index.failed", True)

            # Only our own messages are safe to log: a provider error can echo what was sent to it.
            safe_error = str(e) if isinstance(e, DomainError) else type(e).__name__
            logger.error(
                "Document processing failed for document_id=%s: %s",
                document_id,
                safe_error,
                extra={"document_id": document_id, "error": safe_error},
            )
