import pytest

from maritime.core.exceptions import DomainError
from maritime.modules.rag.domain.value_objects import RetrievedChunk
from maritime.modules.rag.infrastructure.llm.mock_llm import MockDeterministicLlmAdapter
from maritime.modules.rag.infrastructure.llm.pydantic_ai_adapter import PydanticAiLlmAdapter


@pytest.fixture
def maritime_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="chk-1",
            document_id="doc-maersk-1",
            document_name="contrato_maersk_mediterraneo_2026.pdf",
            page_number=1,
            text="Tarifas acordadas para el servicio Mediterráneo: Tarifa Base por TEU: $1,250 USD.",
            similarity_score=0.91,
        ),
        RetrievedChunk(
            chunk_id="chk-2",
            document_id="doc-maersk-1",
            document_name="contrato_maersk_mediterraneo_2026.pdf",
            page_number=2,
            text="Cláusula de Demoras: El importador dispondrá de 10 días libres en terminal.",
            similarity_score=0.87,
        ),
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_llm_answers_demurrage_query_with_citations(
    maritime_chunks: list[RetrievedChunk],
) -> None:
    adapter = MockDeterministicLlmAdapter()
    response = await adapter.generate_answer(
        query="¿Cuántos días libres de demoras se contemplan?",
        context_chunks=maritime_chunks,
    )

    assert response.has_sufficient_evidence is True
    assert "10 días libres" in response.answer or "demoras" in response.answer.lower()
    assert len(response.citations) > 0
    assert response.citations[0].document_name == "contrato_maersk_mediterraneo_2026.pdf"
    assert response.citations[0].page_number == 2
    assert "10 días libres en terminal" in response.citations[0].snippet_text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_llm_answers_rate_query_with_citations(
    maritime_chunks: list[RetrievedChunk],
) -> None:
    adapter = MockDeterministicLlmAdapter()
    response = await adapter.generate_answer(
        query="¿Cuál es la tarifa por contenedor TEU?",
        context_chunks=maritime_chunks,
    )

    assert response.has_sufficient_evidence is True
    assert "$1,250 USD" in response.answer
    assert len(response.citations) > 0
    assert response.citations[0].page_number == 1
    assert "$1,250 USD" in response.citations[0].snippet_text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_llm_abstains_when_query_unrelated(
    maritime_chunks: list[RetrievedChunk],
) -> None:
    adapter = MockDeterministicLlmAdapter()
    response = await adapter.generate_answer(
        query="¿Cuál es la política para vuelos comerciales de pasajeros?",
        context_chunks=maritime_chunks,
    )

    assert response.has_sufficient_evidence is False
    assert "No hay evidencia suficiente" in response.answer
    assert response.citations == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_llm_answers_greeting() -> None:
    adapter = MockDeterministicLlmAdapter()
    response = await adapter.generate_answer(
        query="Hola, ¿cómo estás?",
        context_chunks=[],
    )

    assert response.has_sufficient_evidence is True
    assert "Naviera Portecho" in response.answer
    assert response.citations == []
    assert response.confidence_score is None


@pytest.mark.unit
def test_pydantic_ai_adapter_initializes_openai_with_custom_base_url() -> None:
    adapter = PydanticAiLlmAdapter(
        api_key="sk-test-key",
        provider="openai",
        model_name="gpt-4o-mini",
        base_url="https://custom-openai.internal/v1",
    )
    assert adapter.provider_name == "openai"
    assert adapter.model_name == "gpt-4o-mini"
    assert adapter.base_url == "https://custom-openai.internal/v1"
    assert adapter.timeout == 60.0


@pytest.mark.unit
def test_pydantic_ai_adapter_custom_timeout() -> None:
    adapter = PydanticAiLlmAdapter(
        api_key="sk-test-key",
        provider="openai",
        model_name="deepseek-ai/deepseek-v4.1-flash",
        base_url="https://integrate.api.nvidia.com/v1",
        timeout=120.0,
    )
    assert adapter.timeout == 120.0


@pytest.mark.unit
def test_pydantic_ai_adapter_initializes_gemini() -> None:
    adapter = PydanticAiLlmAdapter(
        api_key="test-gemini-key",
        provider="gemini",
        model_name="gemini-1.5-flash",
        base_url=None,
    )
    assert adapter.provider_name == "gemini"
    assert adapter.model_name == "gemini-1.5-flash"


@pytest.mark.unit
def test_pydantic_ai_adapter_raises_for_unsupported_provider() -> None:
    with pytest.raises(DomainError, match="Unsupported LLM provider"):
        PydanticAiLlmAdapter(
            api_key="test-key",
            provider="unsupported_vendor",
            model_name="test-model",
            base_url=None,
        )
