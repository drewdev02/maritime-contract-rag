from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from maritime.core.events.in_memory import InMemoryEventBus
from maritime.infrastructure.config import Settings
from maritime.infrastructure.database.session import Base
from maritime.infrastructure.di.container import ApplicationContainer
from maritime.infrastructure.di.deps import get_container, get_db_session
from maritime.main import app
from maritime.modules.indexing.infrastructure.embeddings.mock_embedding import (
    MockDeterministicEmbeddingAdapter,
)
from maritime.modules.indexing.infrastructure.models import DocumentChunkModel
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.value_objects import (
    ContentHash,
    DocumentId,
)
from maritime.modules.ingestion.infrastructure.repository import SqlAlchemyDocumentRepository


@pytest.fixture(scope="module")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    yield container
    container.stop()


@pytest.fixture
async def e2e_rag_client(
    postgres_container: PostgresContainer,
    tmp_path: Path,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    raw_url = postgres_container.get_connection_url()
    async_url = raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )

    engine = create_async_engine(async_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("TRUNCATE TABLE document_chunks, contracts_documents RESTART IDENTITY CASCADE;")
        )

    event_bus = InMemoryEventBus()
    storage_path = tmp_path / "contracts"
    storage_path.mkdir(parents=True, exist_ok=True)
    test_settings = Settings(
        DATABASE_URL=async_url,
        STORAGE_PATH=str(storage_path),
        LLM_PROVIDER="mock",
        EMBEDDING_PROVIDER="mock",
        EMBEDDING_API_KEY="",
        EMBEDDING_BASE_URL=None,
    )

    container = ApplicationContainer(
        session_factory=session_factory,
        event_bus=event_bus,
        settings=test_settings,
    )

    # Seed a READY document with vector embeddings
    embedder = MockDeterministicEmbeddingAdapter()
    async with session_factory() as session:
        repo = SqlAlchemyDocumentRepository(session=session)
        doc_id = DocumentId.generate()
        doc = ContractDocument.create(
            id=doc_id,
            filename="contrato_maersk_e2e.pdf",
            content_hash=ContentHash("a" * 64),
            size_bytes=2048,
        )
        doc.mark_as_ready(total_chunks=2)
        await repo.save(doc)

        chunk1_text = "Tarifa Base por TEU: $1,250 USD para tráfico transatlántico."
        chunk2_text = "Cláusula de Demoras: El cliente dispondrá de 10 días libres en terminal."

        c1 = DocumentChunkModel(
            id="chk-e2e-1",
            document_id=doc_id.value,
            chunk_index=0,
            page_number=1,
            start_char_idx=0,
            end_char_idx=len(chunk1_text),
            text=chunk1_text,
            embedding=embedder.embed_text(chunk1_text),
        )
        c2 = DocumentChunkModel(
            id="chk-e2e-2",
            document_id=doc_id.value,
            chunk_index=1,
            page_number=2,
            start_char_idx=0,
            end_char_idx=len(chunk2_text),
            text=chunk2_text,
            embedding=embedder.embed_text(chunk2_text),
        )
        session.add_all([c1, c2])
        await session.commit()

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_db_session] = override_get_db_session

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e_query_contracts_with_pgvector_and_citations(
    e2e_rag_client: httpx.AsyncClient,
) -> None:
    # 1. Query with factual answer and exact citation
    response = await e2e_rag_client.post(
        "/api/v1/query",
        json={"query": "¿Cuántos días libres de demoras se contemplan?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["has_sufficient_evidence"] is True
    assert "10 días libres" in data["answer"] or "demoras" in data["answer"].lower()
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["document_name"] == "contrato_maersk_e2e.pdf"
    assert data["citations"][0]["page_number"] == 2
    assert "10 días libres en terminal" in data["citations"][0]["snippet_text"]

    # 2. Query without evidence in the contracts
    abstention_response = await e2e_rag_client.post(
        "/api/v1/query",
        json={"query": "¿Cuál es la política para vuelos espaciales comerciales?"},
    )

    assert abstention_response.status_code == 200
    abs_data = abstention_response.json()
    assert abs_data["has_sufficient_evidence"] is False
    assert "No hay evidencia suficiente" in abs_data["answer"]
    assert abs_data["citations"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e_query_contracts_stream(
    e2e_rag_client: httpx.AsyncClient,
) -> None:
    async with e2e_rag_client.stream(
        "POST",
        "/api/v1/query/stream",
        json={"query": "¿Cuántos días libres de demoras se contemplan?"},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = ""
        async for chunk in response.aiter_text():
            body += chunk

    assert "event: token" in body
    assert "event: meta" in body
    assert "event: done" in body
    assert "10 días libres" in body
    assert "contrato_maersk_e2e.pdf" in body
