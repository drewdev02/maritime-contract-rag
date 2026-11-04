from typing import Any
from unittest.mock import AsyncMock

import httpx
import litellm
import pytest
from httpx import ASGITransport
from tenacity import wait_none

from maritime.core.exceptions import (
    EmbeddingServiceError,
    LlmServiceError,
    ProviderError,
    classify_provider_failure,
)
from maritime.infrastructure.di.deps import get_ask_contract_question_use_case
from maritime.main import app
from maritime.modules.indexing.infrastructure.embeddings.litellm_embedding import (
    LiteLlmEmbeddingAdapter,
)
from maritime.modules.rag.application.use_cases import AskContractQuestionUseCase
from maritime.modules.rag.infrastructure.llm.pydantic_ai_adapter import (
    PydanticAiLlmAdapter,
    PydanticRagAnswer,
)


class FakeRateLimit(Exception):
    status_code = 429


class UnexpectedModelBehavior(Exception):
    pass


def _adapter() -> PydanticAiLlmAdapter:
    adapter = PydanticAiLlmAdapter(
        api_key="k", provider="openai", model_name="m", base_url="http://llm.test/v1"
    )
    adapter._wait = wait_none()
    return adapter


class _Result:
    def __init__(self) -> None:
        self.output = PydanticRagAnswer(answer="ok", citations=[], has_sufficient_evidence=True)
        self.usage = type("U", (), {"input_tokens": 1, "output_tokens": 2})()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (FakeRateLimit("too many"), "quota"),
        (RuntimeError("RESOURCE_EXHAUSTED: quota exceeded"), "quota"),
        (UnexpectedModelBehavior("Exceeded maximum retries for output validation"), "malformed"),
        (httpx.ConnectTimeout("timeout"), "unavailable"),
        (RuntimeError("boom"), "unavailable"),
    ],
)
def test_classify_provider_failure(exc: Exception, kind: str) -> None:
    assert classify_provider_failure(exc) == kind


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_retries_transient_failure_then_succeeds() -> None:
    adapter = _adapter()
    agent = AsyncMock()
    agent.run.side_effect = [httpx.ConnectTimeout("t"), httpx.ReadTimeout("t"), _Result()]
    adapter._agent = agent

    response = await adapter.generate_answer(query="¿tarifa?", context_chunks=[])

    assert response.answer == "ok"
    assert agent.run.await_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "kind", "status"),
    [
        (FakeRateLimit("429"), "quota", 429),
        (UnexpectedModelBehavior("bad json"), "malformed", 502),
        (httpx.ConnectError("down"), "unavailable", 503),
    ],
)
async def test_llm_raises_typed_error_after_exhausting_retries(
    exc: Exception, kind: str, status: int
) -> None:
    adapter = _adapter()
    agent = AsyncMock()
    agent.run.side_effect = exc
    adapter._agent = agent

    with pytest.raises(LlmServiceError) as info:
        await adapter.generate_answer(query="¿tarifa?", context_chunks=[])

    assert (info.value.kind, info.value.http_status) == (kind, status)
    assert agent.run.await_count == adapter.max_attempts
    assert "¿tarifa?" not in info.value.user_message


@pytest.mark.unit
def test_embedding_adapter_sets_timeout_retries_and_classifies_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def fail(**kwargs: Any) -> Any:
        seen.update(kwargs)
        raise litellm.exceptions.RateLimitError("quota", llm_provider="gemini", model="m")

    monkeypatch.setattr(litellm, "embedding", fail)
    adapter = LiteLlmEmbeddingAdapter(
        api_key="k", model="gemini/text-embedding-004", base_url=None, dimensions=768, timeout=7.0
    )

    with pytest.raises(EmbeddingServiceError) as info:
        adapter.embed_text("hola")

    assert info.value.kind == "quota"
    assert seen["timeout"] == 7.0
    assert seen["num_retries"] == 3


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "status"), [("quota", 429), ("unavailable", 503), ("malformed", 502)]
)
async def test_query_endpoint_maps_provider_errors_to_readable_http_errors(
    kind: str, status: int
) -> None:
    use_case = AsyncMock(spec=AskContractQuestionUseCase)
    use_case.execute.side_effect = ProviderError("raw provider detail with secrets", kind=kind)
    app.dependency_overrides[get_ask_contract_question_use_case] = lambda: use_case
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/query", json={"query": "¿tarifa?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == status
    detail = response.json()["detail"]
    assert "secrets" not in detail
    assert detail
