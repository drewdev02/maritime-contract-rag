from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from maritime.core.exceptions import InvariantViolationError
from maritime.modules.indexing.domain.ports import IEmbeddingService
from maritime.modules.rag.application.use_cases import AskContractQuestionUseCase
from maritime.modules.rag.domain.ports import ILlmService, IQueryEngine
from maritime.modules.rag.domain.services import StrictCitationValidator
from maritime.modules.rag.domain.value_objects import (
    Citation,
    RagResponse,
    RetrievedChunk,
    StreamChunk,
    StreamDeltaChunk,
    StreamMetaChunk,
)


@pytest.fixture
def sample_retrieved_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id="chk-001",
            document_id="doc-001",
            document_name="contrato_maersk_2026.pdf",
            page_number=1,
            text="La tarifa acordada por contenedor de 20 pies (TEU) es de $1,250 USD.",
            similarity_score=0.88,
        ),
        RetrievedChunk(
            chunk_id="chk-002",
            document_id="doc-001",
            document_name="contrato_maersk_2026.pdf",
            page_number=2,
            text="El cliente dispondrá de 10 días libres de demoras en terminal portuaria.",
            similarity_score=0.82,
        ),
    ]


@pytest.mark.unit
def test_citation_value_object() -> None:
    citation = Citation(
        chunk_id="chk-001",
        document_id="doc-001",
        document_name="contrato.pdf",
        page_number=1,
        snippet_text="Tarifa $1,250 USD",
    )
    assert citation.chunk_id == "chk-001"
    assert citation.document_id == "doc-001"
    assert citation.page_number == 1
    assert citation.snippet_text == "Tarifa $1,250 USD"


@pytest.mark.unit
def test_strict_citation_validator_accepts_valid_citation(
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    validator = StrictCitationValidator()
    valid_citation = Citation(
        chunk_id="chk-001",
        document_id="doc-001",
        document_name="contrato_maersk_2026.pdf",
        page_number=1,
        snippet_text="tarifa acordada por contenedor de 20 pies",
    )

    validated = validator.validate(
        citations=[valid_citation],
        context_chunks=sample_retrieved_chunks,
    )
    assert len(validated) == 1
    assert validated[0].chunk_id == "chk-001"


@pytest.mark.unit
def test_strict_citation_validator_rejects_hallucinated_text(
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    validator = StrictCitationValidator()
    fake_citation = Citation(
        chunk_id="chk-001",
        document_id="doc-001",
        document_name="contrato_maersk_2026.pdf",
        page_number=1,
        snippet_text="La tarifa de demoras es de $500 por hora extra.",  # Not in chunk
    )

    validated = validator.validate(
        citations=[fake_citation],
        context_chunks=sample_retrieved_chunks,
    )
    assert len(validated) == 0


@pytest.mark.unit
def test_strict_citation_validator_rejects_mismatched_document(
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    validator = StrictCitationValidator()
    mismatched_citation = Citation(
        chunk_id="chk-999",
        document_id="doc-unknown",
        document_name="contrato_inventado.pdf",
        page_number=1,
        snippet_text="tarifa acordada",
    )

    validated = validator.validate(
        citations=[mismatched_citation],
        context_chunks=sample_retrieved_chunks,
    )
    assert len(validated) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_contract_question_use_case_success(
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    mock_query_engine = AsyncMock(spec=IQueryEngine)
    mock_query_engine.retrieve_chunks.return_value = sample_retrieved_chunks

    mock_llm_service = AsyncMock(spec=ILlmService)
    expected_citation = Citation(
        chunk_id="chk-001",
        document_id="doc-001",
        document_name="contrato_maersk_2026.pdf",
        page_number=1,
        snippet_text="tarifa acordada por contenedor de 20 pies",
    )
    mock_llm_service.generate_answer.return_value = RagResponse(
        answer="La tarifa base por TEU es de $1,250 USD.",
        citations=[expected_citation],
        has_sufficient_evidence=True,
        confidence_score=0.92,
    )

    mock_embedding_service = MagicMock(spec=IEmbeddingService)
    mock_embedding_service.embed_text.return_value = [0.1] * 768

    use_case = AskContractQuestionUseCase(
        query_engine=mock_query_engine,
        llm_service=mock_llm_service,
        embedding_service=mock_embedding_service,
        citation_validator=StrictCitationValidator(),
    )

    response = await use_case.execute(query="¿Cuál es la tarifa por TEU?")

    assert response.has_sufficient_evidence is True
    assert "1,250 USD" in response.answer
    assert len(response.citations) == 1
    assert response.citations[0].document_id == "doc-001"
    mock_embedding_service.embed_text.assert_called_once_with("¿Cuál es la tarifa por TEU?")
    mock_query_engine.retrieve_chunks.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_contract_question_use_case_abstains_when_no_chunks() -> None:
    mock_query_engine = AsyncMock(spec=IQueryEngine)
    mock_query_engine.retrieve_chunks.return_value = []

    mock_llm_service = AsyncMock(spec=ILlmService)
    mock_llm_service.generate_answer.return_value = RagResponse(
        answer="No hay evidencia suficiente en los contratos disponibles para responder a esta pregunta.",
        citations=[],
        has_sufficient_evidence=False,
        confidence_score=0.0,
    )

    mock_embedding_service = MagicMock(spec=IEmbeddingService)
    mock_embedding_service.embed_text.return_value = [0.1] * 768

    use_case = AskContractQuestionUseCase(
        query_engine=mock_query_engine,
        llm_service=mock_llm_service,
        embedding_service=mock_embedding_service,
        citation_validator=StrictCitationValidator(),
    )

    response = await use_case.execute(query="¿Cuál es la política de transporte aéreo?")

    assert response.has_sufficient_evidence is False
    assert "No hay evidencia suficiente" in response.answer
    assert response.citations == []
    mock_llm_service.generate_answer.assert_awaited_once_with(
        query="¿Cuál es la política de transporte aéreo?",
        context_chunks=[],
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_contract_question_use_case_abstains_when_similarity_low() -> None:
    low_score_chunks = [
        RetrievedChunk(
            chunk_id="chk-low",
            document_id="doc-low",
            document_name="contrato.pdf",
            page_number=1,
            text="Texto irrelevante",
            similarity_score=0.15,  # Below similarity threshold
        )
    ]
    mock_query_engine = AsyncMock(spec=IQueryEngine)
    mock_query_engine.retrieve_chunks.return_value = low_score_chunks

    mock_llm_service = AsyncMock(spec=ILlmService)
    mock_llm_service.generate_answer.return_value = RagResponse(
        answer="No hay evidencia suficiente en los contratos disponibles para responder a esta pregunta.",
        citations=[],
        has_sufficient_evidence=False,
        confidence_score=0.0,
    )

    mock_embedding_service = MagicMock(spec=IEmbeddingService)
    mock_embedding_service.embed_text.return_value = [0.1] * 768

    use_case = AskContractQuestionUseCase(
        query_engine=mock_query_engine,
        llm_service=mock_llm_service,
        embedding_service=mock_embedding_service,
        citation_validator=StrictCitationValidator(),
        similarity_threshold=0.30,
    )

    response = await use_case.execute(query="Pregunta sin coincidencia vectorial")

    assert response.has_sufficient_evidence is False
    assert "No hay evidencia suficiente" in response.answer
    assert response.citations == []
    mock_llm_service.generate_answer.assert_awaited_once_with(
        query="Pregunta sin coincidencia vectorial",
        context_chunks=[],
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_contract_question_use_case_greeting_responds_naturally() -> None:
    mock_query_engine = AsyncMock(spec=IQueryEngine)
    mock_query_engine.retrieve_chunks.return_value = []

    mock_llm_service = AsyncMock(spec=ILlmService)
    mock_llm_service.generate_answer.return_value = RagResponse(
        answer="¡Hola! Soy el asistente inteligente de Naviera Portecho. ¿En qué puedo asistirte hoy?",
        citations=[],
        has_sufficient_evidence=True,
        confidence_score=None,
    )

    mock_embedding_service = MagicMock(spec=IEmbeddingService)
    mock_embedding_service.embed_text.return_value = [0.1] * 768

    use_case = AskContractQuestionUseCase(
        query_engine=mock_query_engine,
        llm_service=mock_llm_service,
        embedding_service=mock_embedding_service,
        citation_validator=StrictCitationValidator(),
    )

    response = await use_case.execute(query="hola como estas?")

    assert response.has_sufficient_evidence is True
    assert "Naviera Portecho" in response.answer
    assert response.citations == []
    assert response.confidence_score is None
    mock_llm_service.generate_answer.assert_awaited_once_with(
        query="hola como estas?",
        context_chunks=[],
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_contract_question_use_case_empty_query_raises_error() -> None:
    use_case = AskContractQuestionUseCase(
        query_engine=AsyncMock(spec=IQueryEngine),
        llm_service=AsyncMock(spec=ILlmService),
        embedding_service=MagicMock(spec=IEmbeddingService),
        citation_validator=StrictCitationValidator(),
    )

    with pytest.raises(InvariantViolationError):
        await use_case.execute(query="   ")


@pytest.mark.unit
def test_stream_chunks_value_objects() -> None:
    delta = StreamDeltaChunk(delta="Hola")
    assert delta.delta == "Hola"

    meta = StreamMetaChunk(citations=[], has_sufficient_evidence=True, confidence_score=0.95)
    assert meta.citations == []
    assert meta.has_sufficient_evidence is True
    assert meta.confidence_score == 0.95


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_llm_adapter_streaming(sample_retrieved_chunks: list[RetrievedChunk]) -> None:
    from maritime.modules.rag.infrastructure.llm.mock_llm import MockDeterministicLlmAdapter

    adapter = MockDeterministicLlmAdapter()
    chunks = []
    async for chunk in adapter.generate_answer_stream(
        query="¿Cuántos días libres de demoras hay?",
        context_chunks=sample_retrieved_chunks,
    ):
        chunks.append(chunk)

    deltas = [c for c in chunks if isinstance(c, StreamDeltaChunk)]
    metas = [c for c in chunks if isinstance(c, StreamMetaChunk)]

    assert len(deltas) > 0
    full_text = "".join(d.delta for d in deltas)
    assert "10 días libres" in full_text
    assert len(metas) == 1
    assert metas[0].has_sufficient_evidence is True
    assert len(metas[0].citations) == 1
    assert metas[0].citations[0].document_name == "contrato_maersk_2026.pdf"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ask_contract_question_use_case_execute_stream(
    sample_retrieved_chunks: list[RetrievedChunk],
) -> None:
    mock_query_engine = AsyncMock(spec=IQueryEngine)
    mock_query_engine.retrieve_chunks.return_value = sample_retrieved_chunks

    expected_citation = Citation(
        chunk_id="chk-001",
        document_id="doc-001",
        document_name="contrato_maersk_2026.pdf",
        page_number=1,
        snippet_text="tarifa acordada por contenedor de 20 pies",
    )

    async def fake_stream(
        query: str, context_chunks: list[RetrievedChunk]
    ) -> AsyncIterator[StreamChunk]:
        yield StreamDeltaChunk(delta="La tarifa base ")
        yield StreamDeltaChunk(delta="es de $1,250 USD.")
        yield StreamMetaChunk(
            citations=[expected_citation],
            has_sufficient_evidence=True,
            confidence_score=0.92,
        )

    mock_llm_service = MagicMock(spec=ILlmService)
    mock_llm_service.generate_answer_stream = fake_stream

    mock_embedding_service = MagicMock(spec=IEmbeddingService)
    mock_embedding_service.embed_text.return_value = [0.1] * 768

    use_case = AskContractQuestionUseCase(
        query_engine=mock_query_engine,
        llm_service=mock_llm_service,
        embedding_service=mock_embedding_service,
        citation_validator=StrictCitationValidator(),
    )

    streamed_items = []
    async for item in use_case.execute_stream(query="¿Cuál es la tarifa por TEU?"):
        streamed_items.append(item)

    deltas = [item for item in streamed_items if isinstance(item, StreamDeltaChunk)]
    metas = [item for item in streamed_items if isinstance(item, StreamMetaChunk)]

    assert len(deltas) == 2
    assert "".join(d.delta for d in deltas) == "La tarifa base es de $1,250 USD."
    assert len(metas) == 1
    assert metas[0].has_sufficient_evidence is True
    assert len(metas[0].citations) == 1
    assert metas[0].citations[0].chunk_id == "chk-001"
