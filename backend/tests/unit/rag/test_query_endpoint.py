from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import ASGITransport

from maritime.infrastructure.di.deps import get_ask_contract_question_use_case
from maritime.main import app
from maritime.modules.rag.application.use_cases import AskContractQuestionUseCase
from maritime.modules.rag.domain.value_objects import Citation, RagResponse


@pytest.fixture
def mock_use_case() -> AsyncMock:
    return AsyncMock(spec=AskContractQuestionUseCase)


@pytest.fixture
async def client(mock_use_case: AsyncMock) -> AsyncGenerator[httpx.AsyncClient, None]:
    app.dependency_overrides[get_ask_contract_question_use_case] = lambda: mock_use_case
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_contracts_endpoint_success(
    client: httpx.AsyncClient,
    mock_use_case: AsyncMock,
) -> None:
    mock_use_case.execute.return_value = RagResponse(
        answer="La tarifa base por TEU es de $1,250 USD.",
        citations=[
            Citation(
                chunk_id="chk-1",
                document_id="doc-1",
                document_name="contrato_maersk.pdf",
                page_number=1,
                snippet_text="Tarifa Base por TEU: $1,250 USD",
            )
        ],
        has_sufficient_evidence=True,
        confidence_score=0.95,
    )

    response = await client.post(
        "/api/v1/query",
        json={"query": "¿Cuál es la tarifa por TEU?", "top_k": 3},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "La tarifa base por TEU es de $1,250 USD."
    assert data["has_sufficient_evidence"] is True
    assert data["confidence_score"] == 0.95
    assert len(data["citations"]) == 1
    assert data["citations"][0]["document_name"] == "contrato_maersk.pdf"
    assert data["citations"][0]["page_number"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_contracts_endpoint_abstention(
    client: httpx.AsyncClient,
    mock_use_case: AsyncMock,
) -> None:
    mock_use_case.execute.return_value = RagResponse(
        answer="No hay evidencia suficiente en los contratos disponibles para responder a esta pregunta.",
        citations=[],
        has_sufficient_evidence=False,
        confidence_score=0.0,
    )

    response = await client.post(
        "/api/v1/query",
        json={"query": "Consulta sin evidencia"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["has_sufficient_evidence"] is False
    assert "No hay evidencia suficiente" in data["answer"]
    assert data["citations"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_query_contracts_endpoint_validation_errors(client: httpx.AsyncClient) -> None:
    # 1. Empty query
    res1 = await client.post("/api/v1/query", json={"query": ""})
    assert res1.status_code == 422

    # 2. Extra forbid field
    res2 = await client.post(
        "/api/v1/query",
        json={"query": "¿Tarifas?", "unauthorized_extra_field": True},
    )
    assert res2.status_code == 422
