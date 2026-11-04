"""Spans that explain where time and failures go: RAG steps, the LLM stream, indexing, HTTP calls.

Spans are captured with an in-memory exporter, so the assertions are about what a trace in Jaeger
would show. Several tests also pin down what must *never* be in a span (messages, URL secrets).
"""

import asyncio
import threading
from collections.abc import AsyncIterator, Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from tests.unit.indexing.test_index_document_use_case import (
    DummyChunker,
    DummyEmbedding,
    DummyParser,
    InMemoryChunkRepository,
    InMemoryDocumentRepo,
    InMemoryStorage,
)

from maritime.core.exceptions import LlmServiceError
from maritime.core.telemetry.tracer import instrument_http_clients, setup_telemetry, span
from maritime.modules.indexing.application.use_cases import IndexDocumentUseCase
from maritime.modules.ingestion.domain.entities import ContractDocument
from maritime.modules.ingestion.domain.value_objects import ContentHash, DocumentId
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
from maritime.modules.rag.infrastructure.llm.pydantic_ai_adapter import (
    PydanticAiLlmAdapter,
    PydanticCitation,
    PydanticRagAnswer,
)


@pytest.fixture
def exporter() -> Generator[InMemorySpanExporter, None, None]:
    setup_telemetry(service_name="maritime-test")
    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)
    memory = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    yield memory
    memory.clear()


def _by_name(exporter: InMemorySpanExporter, name: str) -> ReadableSpan:
    matches = [s for s in exporter.get_finished_spans() if s.name == name]
    assert len(matches) == 1, f"expected one '{name}' span, found {len(matches)}"
    return matches[0]


# --- span() never leaks exception messages ----------------------------------------------------


@pytest.mark.unit
def test_a_failing_span_records_the_exception_type_and_never_its_message(
    exporter: InMemorySpanExporter,
) -> None:
    with pytest.raises(ValueError), span("unit.fails"):
        raise ValueError("Cláusula 5: tarifa confidencial de 150 USD")

    failed = _by_name(exporter, "unit.fails")
    assert failed.status.status_code == StatusCode.ERROR
    assert failed.status.description == "ValueError"
    assert (failed.attributes or {})["error.type"] == "ValueError"
    assert failed.events == ()  # no exception event, which would carry the message
    assert "confidencial" not in str(failed.to_json())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cancellation_is_not_an_error(exporter: InMemorySpanExporter) -> None:
    async def work() -> None:
        with span("unit.cancelled"):
            await asyncio.sleep(10)

    task = asyncio.create_task(work())
    await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert _by_name(exporter, "unit.cancelled").status.status_code == StatusCode.UNSET


# --- RAG: retrieval decision and citation validation ------------------------------------------


def _chunk(n: int, score: float, text: str = "Clausula 3. Preaviso de 90 dias.") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"c{n}",
        document_id="d1",
        document_name="hapag.pdf",
        page_number=n,
        text=text,
        similarity_score=score,
    )


class FakeEngine(IQueryEngine):
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    async def retrieve_chunks(
        self, query_vector: list[float], top_k: int = 5, document_id: str | None = None
    ) -> list[RetrievedChunk]:
        return self._chunks


class FakeLlm(ILlmService):
    def __init__(self, citations: list[Citation], evidence: bool = True) -> None:
        self._citations = citations
        self._evidence = evidence

    async def generate_answer(
        self, query: str, context_chunks: list[RetrievedChunk]
    ) -> RagResponse:
        return RagResponse(
            answer="90 dias",
            citations=self._citations,
            has_sufficient_evidence=self._evidence,
            confidence_score=None,
        )

    def generate_answer_stream(
        self, query: str, context_chunks: list[RetrievedChunk]
    ) -> AsyncIterator[StreamChunk]:
        async def gen() -> AsyncIterator[StreamChunk]:
            yield StreamDeltaChunk(delta="90 dias")
            yield StreamMetaChunk(
                citations=self._citations,
                has_sufficient_evidence=self._evidence,
                confidence_score=None,
            )

        return gen()


def _citation(snippet: str, n: int = 1) -> Citation:
    return Citation(
        chunk_id=f"c{n}",
        document_id="d1",
        document_name="hapag.pdf",
        page_number=n,
        snippet_text=snippet,
    )


def _use_case(chunks: list[RetrievedChunk], llm: ILlmService) -> AskContractQuestionUseCase:
    return AskContractQuestionUseCase(
        query_engine=FakeEngine(chunks),
        llm_service=llm,
        embedding_service=DummyEmbedding(),
        citation_validator=StrictCitationValidator(),
        similarity_threshold=0.25,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieval_span_explains_what_was_found_and_what_passed_the_threshold(
    exporter: InMemorySpanExporter,
) -> None:
    chunks = [_chunk(1, 0.61), _chunk(2, 0.30), _chunk(3, 0.10)]
    use_case = _use_case(chunks, FakeLlm([_citation("preaviso de 90 dias")]))

    await use_case.execute("¿Preaviso?")

    attrs = _by_name(exporter, "rag.retrieve").attributes or {}
    assert attrs["rag.retrieved_chunks"] == 3
    assert attrs["rag.chunks_above_threshold"] == 2
    assert attrs["rag.threshold"] == 0.25
    assert attrs["rag.top_similarity"] == 0.61
    assert attrs["rag.context_empty"] is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retrieval_span_shows_when_nothing_was_close_enough(
    exporter: InMemorySpanExporter,
) -> None:
    use_case = _use_case([_chunk(1, 0.05)], FakeLlm([], evidence=False))

    await use_case.execute("¿Vacaciones?")

    attrs = _by_name(exporter, "rag.retrieve").attributes or {}
    assert attrs["rag.chunks_above_threshold"] == 0
    assert attrs["rag.context_empty"] is True
    assert attrs["rag.top_similarity"] == 0.05


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_citation_validation_span_counts_accepted_and_rejected_citations(
    exporter: InMemorySpanExporter, streaming: bool
) -> None:
    llm = FakeLlm([_citation("preaviso de 90 dias"), _citation("texto inventado por el modelo", 2)])
    use_case = _use_case([_chunk(1, 0.6)], llm)

    if streaming:
        _ = [chunk async for chunk in use_case.execute_stream("¿Preaviso?")]
    else:
        await use_case.execute("¿Preaviso?")

    attrs = _by_name(exporter, "rag.validate_citations").attributes or {}
    assert attrs["rag.citations.proposed"] == 2
    assert attrs["rag.citations.accepted"] == 1
    assert attrs["rag.citations.rejected"] == 1
    assert attrs["rag.chunks_in_context"] == 1


# --- indexing: a handled failure still shows up as an error -----------------------------------


async def _index(parser: DummyParser) -> None:
    repo, storage = InMemoryDocumentRepo(), InMemoryStorage()
    doc_id = DocumentId.generate()
    doc = ContractDocument.create(
        id=doc_id, filename="a.pdf", content_hash=ContentHash("e" * 64), size_bytes=10
    )
    doc.pull_events()
    await repo.save(doc)
    await storage.save(doc_id.value, doc.filename, b"%PDF-1.4 dummy")
    from maritime.core.events.in_memory import InMemoryEventBus

    use_case = IndexDocumentUseCase(
        document_repository=repo,
        chunk_repository=InMemoryChunkRepository(),
        file_storage=storage,
        pdf_parser=parser,
        chunking_service=DummyChunker(),
        embedding_service=DummyEmbedding(),
        event_bus=InMemoryEventBus(),
    )
    await use_case.execute(doc_id.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_document_that_fails_marks_its_span_as_an_error_with_a_readable_reason(
    exporter: InMemorySpanExporter,
) -> None:
    await _index(DummyParser(should_fail_pw=True))

    document_span = _by_name(exporter, "index.document")
    assert document_span.status.status_code == StatusCode.ERROR
    assert document_span.status.description == "El documento está protegido por contraseña"
    attrs = document_span.attributes or {}
    assert attrs["error.type"] == "PasswordProtectedPdfError"
    assert attrs["index.failed"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_document_that_indexes_fine_leaves_its_span_without_error(
    exporter: InMemorySpanExporter,
) -> None:
    await _index(DummyParser())

    document_span = _by_name(exporter, "index.document")
    assert document_span.status.status_code == StatusCode.UNSET
    assert "index.failed" not in (document_span.attributes or {})


# --- the LLM stream ---------------------------------------------------------------------------


class FakeStreamResponse:
    usage = SimpleNamespace(input_tokens=120, output_tokens=30)

    def __init__(self, partials: list[str], final: PydanticRagAnswer) -> None:
        self._partials = partials
        self._final = final

    async def stream_output(self, debounce_by: float = 0.05) -> AsyncIterator[Any]:
        for text in self._partials:
            await asyncio.sleep(0.001)
            yield SimpleNamespace(answer=text)

    async def get_output(self) -> PydanticRagAnswer:
        return self._final


class FakeRunStream:
    def __init__(self, response: FakeStreamResponse | None, error: Exception | None) -> None:
        self._response = response
        self._error = error

    async def __aenter__(self) -> FakeStreamResponse:
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response

    async def __aexit__(self, *_: object) -> None:
        return None


class FakeAgent:
    def __init__(
        self, response: FakeStreamResponse | None = None, error: Exception | None = None
    ) -> None:
        self._response = response
        self._error = error

    def run_stream(self, prompt: str) -> FakeRunStream:
        return FakeRunStream(self._response, self._error)


def _adapter(agent: FakeAgent) -> PydanticAiLlmAdapter:
    adapter = PydanticAiLlmAdapter(
        api_key="k", provider="openai", model_name="minimax-test", base_url="http://llm.test/v1"
    )
    adapter._agent = agent  # type: ignore[assignment]
    return adapter


def _answer(citations: int) -> PydanticRagAnswer:
    cites = [
        PydanticCitation(
            chunk_id="c1",
            document_id="d1",
            document_name="hapag.pdf",
            page_number=2,
            snippet_text="preaviso escrito de 90 dias",
        )
    ][:citations]
    return PydanticRagAnswer(
        answer="El preaviso es de 90 dias.", citations=cites, has_sufficient_evidence=True
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_stream_span_times_the_first_token_and_records_tokens_and_citations(
    exporter: InMemorySpanExporter,
) -> None:
    response = FakeStreamResponse(
        ["El preaviso", "El preaviso es de 90 dias."], _answer(citations=0)
    )
    adapter = _adapter(FakeAgent(response))

    with span("request.root") as root:
        chunks = [c async for c in adapter.generate_answer_stream("¿Preaviso?", [_chunk(2, 0.6)])]

    assert [type(c).__name__ for c in chunks] == [
        "StreamDeltaChunk",
        "StreamDeltaChunk",
        "StreamMetaChunk",
    ]
    llm_span = _by_name(exporter, "llm.generate_stream")
    attrs = llm_span.attributes or {}
    assert attrs["llm.provider"] == "openai"
    assert attrs["llm.model"] == "minimax-test"
    assert attrs["llm.tokens.input"] == 120
    assert attrs["llm.tokens.output"] == 30
    assert attrs["llm.stream_chunks"] == 2
    assert attrs["llm.citations_returned"] == 0  # the model answered without citing: now visible
    assert float(str(attrs["llm.time_to_first_token_ms"])) >= 0
    # Opened in a separate task, but still a child of the request that triggered it.
    assert llm_span.parent is not None
    assert llm_span.parent.span_id == root.get_span_context().span_id
    prompt_attrs = _by_name(exporter, "rag.build_prompt").attributes or {}
    assert int(str(prompt_attrs["llm.prompt_chars"])) > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_provider_failure_in_the_stream_marks_the_span_and_reaches_the_caller(
    exporter: InMemorySpanExporter,
) -> None:
    adapter = _adapter(FakeAgent(error=httpx.ReadTimeout("secret prompt text echoed by the API")))

    with pytest.raises(LlmServiceError) as failure:
        _ = [c async for c in adapter.generate_answer_stream("¿Preaviso?", [_chunk(2, 0.6)])]

    assert failure.value.kind == "unavailable"
    llm_span = _by_name(exporter, "llm.generate_stream")
    assert llm_span.status.status_code == StatusCode.ERROR
    assert llm_span.status.description == "ReadTimeout"
    assert "secret" not in str(llm_span.to_json())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_abandoning_the_stream_cancels_the_background_read(
    exporter: InMemorySpanExporter,
) -> None:
    response = FakeStreamResponse([f"{'palabra ' * n}" for n in range(1, 50)], _answer(citations=1))
    adapter = _adapter(FakeAgent(response))

    stream = adapter.generate_answer_stream("¿Preaviso?", [_chunk(2, 0.6)])
    first = await anext(stream)
    assert isinstance(first, StreamDeltaChunk)
    await stream.aclose()  # the client went away

    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    assert all(t.done() for t in pending)


# --- outbound HTTP ----------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_: object) -> None:
        return None


@pytest.mark.unit
def test_http_calls_get_a_client_span_that_never_contains_the_url_query(
    exporter: InMemorySpanExporter,
) -> None:
    instrument_http_clients()
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        response = httpx.get(f"http://127.0.0.1:{port}/v1/embeddings?key=SUPER-SECRET-KEY")
        assert response.status_code == 200
    finally:
        server.shutdown()

    client_spans = [s for s in exporter.get_finished_spans() if s.kind == SpanKind.CLIENT]
    assert client_spans, "httpx call produced no client span"
    recorded = str(client_spans[0].to_json())
    assert "SUPER-SECRET-KEY" not in recorded
    attrs = client_spans[0].attributes or {}
    url = attrs.get("url.full") or attrs.get("http.url")
    assert url == f"http://127.0.0.1:{port}/v1/embeddings"
    assert attrs.get("http.response.status_code", attrs.get("http.status_code")) == 200
