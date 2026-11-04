from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from maritime.core.events.in_memory import InMemoryEventBus
from maritime.infrastructure.config import Settings
from maritime.infrastructure.database.session import Base
from maritime.infrastructure.di.container import ApplicationContainer
from maritime.infrastructure.di.deps import get_container, get_db_session
from maritime.main import app


@pytest.fixture(scope="module")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Spins up a real PostgreSQL container with pgvector for E2E testing."""
    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    yield container
    container.stop()


@pytest.fixture
async def e2e_client(
    postgres_container: PostgresContainer,
    tmp_path: Path,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    # Formulate asyncpg connection URL
    raw_url = postgres_container.get_connection_url()
    async_url = raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )

    engine = create_async_engine(async_url, echo=False)
    async_session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    # Initialize tables
    async with engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)

    event_bus = InMemoryEventBus()
    test_settings = Settings(
        DATABASE_URL=async_url,
        STORAGE_PATH=str(tmp_path / "contracts"),
        LLM_PROVIDER="mock",
    )

    container = ApplicationContainer(
        session_factory=async_session_factory,
        event_bus=event_bus,
        settings=test_settings,
    )

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_factory() as session:
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
async def test_e2e_contract_upload_and_idempotency(
    e2e_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    """E2E Test: Tests real multipart upload, database persistence, idempotency, and status listing."""
    sample_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (Contrato Naviera Portecho - Maersk Line) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    filename = "contrato_maersk_e2e.pdf"

    # Step 1: Upload new contract PDF
    files = {"file": (filename, sample_pdf_bytes, "application/pdf")}
    response = await e2e_client.post("/api/v1/documents/upload", files=files)

    assert response.status_code == 201, f"Failed upload: {response.text}"
    data = response.json()
    assert "document_id" in data
    doc_id = data["document_id"]
    assert data["filename"] == filename
    assert data["status"] == "pending"
    assert data["size_bytes"] == len(sample_pdf_bytes)
    assert data["chunk_count"] == 0

    # Verify physical file storage
    saved_file = tmp_path / "contracts" / doc_id / filename
    assert saved_file.is_file(), f"Physical file not found at {saved_file}"
    assert saved_file.read_bytes() == sample_pdf_bytes

    # Step 2: Query document status via GET /{id}
    status_response = await e2e_client.get(f"/api/v1/documents/{doc_id}")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["document_id"] == doc_id
    assert status_data["status"] == "pending"
    assert status_data["filename"] == filename

    # Step 3: Test Idempotency with exact same PDF content
    # Submitting the exact same bytes again must return the existing document without creating duplicates
    dup_files = {"file": ("renamed_duplicate.pdf", sample_pdf_bytes, "application/pdf")}
    dup_response = await e2e_client.post("/api/v1/documents/upload", files=dup_files)

    assert dup_response.status_code == 201
    dup_data = dup_response.json()
    assert dup_data["document_id"] == doc_id, (
        "Idempotency failed: duplicate document created instead of returning existing"
    )

    # Step 4: List all documents and verify total count is strictly 1
    list_response = await e2e_client.get("/api/v1/documents")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["total"] == 1
    assert len(list_data["items"]) == 1
    assert list_data["items"][0]["document_id"] == doc_id
