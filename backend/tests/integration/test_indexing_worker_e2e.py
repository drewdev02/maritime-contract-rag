import io
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from maritime.core.events.in_memory import InMemoryEventBus
from maritime.infrastructure.config import Settings
from maritime.infrastructure.database.session import Base, create_worker_session_factory
from maritime.infrastructure.di.container import ApplicationContainer
from maritime.modules.indexing.infrastructure.models import DocumentChunkModel
from maritime.modules.indexing.tasks.celery_tasks import (
    get_worker_session_factory,
    process_document_task,
    set_worker_session_factory,
)
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
    DocumentStatus,
)
from maritime.modules.ingestion.infrastructure.models import ContractDocumentModel
from maritime.modules.ingestion.infrastructure.repository import SqlAlchemyDocumentRepository
from maritime.modules.ingestion.infrastructure.storage import LocalFileStorageAdapter


def _generate_test_pdf() -> bytes:
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.drawString(100, 750, "Contrato Naviera Portecho - Acuerdos Tarifarios 2026")
    p.drawString(100, 720, "Tarifa Base por TEU: $1,250 USD")
    p.drawString(100, 700, "Plazo de Demoras: 10 dias libres en terminal")
    p.showPage()
    p.save()
    return buffer.getvalue()


@pytest.fixture(scope="module")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    yield container
    container.stop()


@pytest.mark.integration
def test_worker_consecutive_tasks_and_error_fallback(
    postgres_container: PostgresContainer,
    tmp_path: Path,
) -> None:
    """Integration Test: Validates that consecutive Celery tasks run across separate event loops

    in the same process without 'Future attached to a different loop' errors, and verifies
    that unhandled errors transition the document to FAILED in the real PostgreSQL database.
    """
    raw_url = postgres_container.get_connection_url()
    async_url = raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )

    # Initialize tables using temporary engine
    import asyncio

    async def _init_tables() -> None:
        init_engine = create_async_engine(async_url, echo=False)
        async with init_engine.begin() as conn:
            from sqlalchemy import text

            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.run_sync(Base.metadata.create_all)
        await init_engine.dispose()

    asyncio.run(_init_tables())

    worker_factory = create_worker_session_factory(async_url)
    original_factory = get_worker_session_factory()
    set_worker_session_factory(worker_factory)

    storage_path = tmp_path / "contracts"
    storage_path.mkdir(parents=True, exist_ok=True)
    file_storage = LocalFileStorageAdapter(base_path=str(storage_path))

    event_bus = InMemoryEventBus()
    test_settings = Settings(
        DATABASE_URL=async_url,
        STORAGE_PATH=str(storage_path),
        LLM_PROVIDER="mock",
    )
    container = ApplicationContainer(
        session_factory=worker_factory,
        event_bus=event_bus,
        settings=test_settings,
    )

    pdf_bytes = _generate_test_pdf()

    async def _seed_documents() -> tuple[str, str, str]:
        async with worker_factory() as session:
            repo = SqlAlchemyDocumentRepository(session=session)

            # Doc 1: valid
            doc1_id = DocumentId.generate()
            doc1 = ContractDocument.create(
                id=doc1_id,
                filename="contrato_1.pdf",
                content_hash=ContentHash("1" * 64),
                size_bytes=len(pdf_bytes),
            )
            await repo.save(doc1)
            await file_storage.save(
                doc_id=doc1_id.value, filename="contrato_1.pdf", content=pdf_bytes
            )

            # Doc 2: valid
            doc2_id = DocumentId.generate()
            doc2 = ContractDocument.create(
                id=doc2_id,
                filename="contrato_2.pdf",
                content_hash=ContentHash("2" * 64),
                size_bytes=len(pdf_bytes),
            )
            await repo.save(doc2)
            await file_storage.save(
                doc_id=doc2_id.value, filename="contrato_2.pdf", content=pdf_bytes
            )

            # Doc 3: missing physical file (will trigger failure)
            doc3_id = DocumentId.generate()
            doc3 = ContractDocument.create(
                id=doc3_id,
                filename="contrato_3_missing.pdf",
                content_hash=ContentHash("3" * 64),
                size_bytes=100,
            )
            await repo.save(doc3)
            # Intentionally NOT saving to file_storage

            await session.commit()
            return doc1_id.value, doc2_id.value, doc3_id.value

    doc1_id_str, doc2_id_str, doc3_id_str = asyncio.run(_seed_documents())

    try:
        with patch(
            "maritime.modules.indexing.tasks.celery_tasks.get_container",
            return_value=container,
        ):
            # 1. Execute Task 1 (creates Loop 1, indexes doc 1, closes Loop 1)
            res1 = process_document_task(document_id=doc1_id_str)
            assert res1["status"] == "processed"

            # 2. Execute Task 2 immediately in the SAME process (creates Loop 2)
            # If QueuePool were used, this would raise 'Future attached to a different loop'
            res2 = process_document_task(document_id=doc2_id_str)
            assert res2["status"] == "processed"

            # 3. Execute Task 3 which fails due to missing file
            res3 = process_document_task(document_id=doc3_id_str)
            assert res3["status"] == "failed"

            # 4. Verify database state for all 3 documents
            async def _verify_db() -> None:
                async with worker_factory() as session:
                    res_doc1 = await session.execute(
                        select(ContractDocumentModel).where(ContractDocumentModel.id == doc1_id_str)
                    )
                    db_doc1 = res_doc1.scalar_one()
                    assert db_doc1.status == DocumentStatus.READY
                    assert db_doc1.chunk_count > 0

                    res_doc2 = await session.execute(
                        select(ContractDocumentModel).where(ContractDocumentModel.id == doc2_id_str)
                    )
                    db_doc2 = res_doc2.scalar_one()
                    assert db_doc2.status == DocumentStatus.READY
                    assert db_doc2.chunk_count > 0

                    res_doc3 = await session.execute(
                        select(ContractDocumentModel).where(ContractDocumentModel.id == doc3_id_str)
                    )
                    db_doc3 = res_doc3.scalar_one()
                    assert db_doc3.status == DocumentStatus.FAILED
                    assert db_doc3.error_detail is not None
                    assert (
                        "FileNotFoundError" in db_doc3.error_detail
                        or "No such file" in db_doc3.error_detail
                        or "Error al procesar el archivo PDF" in db_doc3.error_detail
                    )

                    # Verify chunks exist in pgvector
                    chunks_res = await session.execute(select(DocumentChunkModel))
                    chunks = chunks_res.scalars().all()
                    assert len(chunks) >= 2

            asyncio.run(_verify_db())
    finally:
        set_worker_session_factory(original_factory)
