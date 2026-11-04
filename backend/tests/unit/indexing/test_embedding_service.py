import math

import pytest

from maritime.core.exceptions import EmbeddingServiceError
from maritime.modules.indexing.infrastructure.embeddings.litellm_embedding import (
    LiteLlmEmbeddingAdapter,
)
from maritime.modules.indexing.infrastructure.embeddings.mock_embedding import (
    MockDeterministicEmbeddingAdapter,
)


@pytest.mark.unit
def test_mock_embedding_dimension_and_normalization() -> None:
    service = MockDeterministicEmbeddingAdapter()
    text = "Cláusula de flete marítimo y demurrage."

    vec = service.embed_text(text)

    assert len(vec) == 768
    assert all(isinstance(x, float) for x in vec)

    # Verify L2 norm is approximately 1.0 (unit vector)
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-4


@pytest.mark.unit
def test_mock_embedding_determinism() -> None:
    service = MockDeterministicEmbeddingAdapter()
    text = "Texto idéntico para verificación de reproducibilidad."

    vec1 = service.embed_text(text)
    vec2 = service.embed_text(text)

    assert vec1 == vec2


@pytest.mark.unit
def test_mock_embedding_distinct_texts() -> None:
    service = MockDeterministicEmbeddingAdapter()
    vec_a = service.embed_text("Contrato de Maersk con tarifas por TEU.")
    vec_b = service.embed_text("Condiciones generales de seguro y avería gruesa.")

    # Dot product should be less than 1.0 (different direction)
    dot_prod = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    assert dot_prod < 0.99


@pytest.mark.unit
def test_mock_embedding_batch() -> None:
    service = MockDeterministicEmbeddingAdapter()
    texts = ["Texto 1", "Texto 2", "Texto 3"]

    vectors = service.embed_batch(texts)

    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 768
        norm = math.sqrt(sum(x * x for x in v))
        assert abs(norm - 1.0) < 1e-4


@pytest.mark.unit
def test_litellm_embedding_initialization_with_custom_base_url() -> None:
    adapter = LiteLlmEmbeddingAdapter(
        api_key="sk-test",
        model="text-embedding-3-small",
        base_url="https://custom-embedding.internal/v1",
        dimensions=768,
    )
    assert adapter.model == "text-embedding-3-small"
    assert adapter.base_url == "https://custom-embedding.internal/v1"
    assert adapter.dimensions == 768

    kwargs = adapter._prepare_kwargs()
    assert kwargs["api_base"] == "https://custom-embedding.internal/v1"
    assert kwargs["dimensions"] == 768


@pytest.mark.unit
def test_litellm_embedding_raises_without_credentials() -> None:
    with pytest.raises(EmbeddingServiceError, match="Se requiere API key o base_url"):
        LiteLlmEmbeddingAdapter(
            api_key=None,
            model="gemini/text-embedding-004",
            base_url=None,
            dimensions=768,
        )


@pytest.mark.unit
def test_litellm_embedding_wraps_api_errors_in_custom_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import litellm

    def mock_fail(*args: object, **kwargs: object) -> None:
        raise ConnectionError("Network unreachable")

    monkeypatch.setattr(litellm, "embedding", mock_fail)
    adapter = LiteLlmEmbeddingAdapter(
        api_key="sk-valid",
        model="text-embedding-3-small",
        base_url=None,
        dimensions=768,
    )

    with pytest.raises(
        EmbeddingServiceError, match="Error durante la generación de embedding"
    ) as exc_info:
        adapter.embed_text("sample maritime clause")

    assert exc_info.value.model == "text-embedding-3-small"


@pytest.mark.unit
def test_litellm_embedding_nvidia_nemotron_direct_kwargs() -> None:
    adapter = LiteLlmEmbeddingAdapter(
        api_key="nvapi-test",
        model="nvidia/nemotron-3.5-embed-8b",
        base_url="https://integrate.api.nvidia.com/v1",
        dimensions=768,
    )
    query_kwargs = adapter._prepare_kwargs(input_type="query")
    assert query_kwargs["input_type"] == "query"
    assert query_kwargs["dimensions"] == 768
    assert "extra_body" not in query_kwargs

    passage_kwargs = adapter._prepare_kwargs(input_type="passage")
    assert passage_kwargs["input_type"] == "passage"
    assert passage_kwargs["dimensions"] == 768


@pytest.mark.unit
def test_litellm_embedding_nvidia_openai_prefix_kwargs() -> None:
    adapter = LiteLlmEmbeddingAdapter(
        api_key="nvapi-test",
        model="openai/nvidia/nemotron-3.5-embed-8b",
        base_url="https://integrate.api.nvidia.com/v1",
        dimensions=768,
    )
    query_kwargs = adapter._prepare_kwargs(input_type="query")
    assert "extra_body" in query_kwargs
    assert query_kwargs["extra_body"]["input_type"] == "query"
    assert query_kwargs["extra_body"]["dimensions"] == 768


@pytest.mark.unit
def test_litellm_embedding_batch_adaptive_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import litellm

    call_counts = {"batch": 0, "single": 0}

    def mock_embedding(**kwargs: object) -> object:
        inputs = kwargs.get("input")
        assert isinstance(inputs, list)
        if len(inputs) > 1:
            call_counts["batch"] += 1
            raise Exception("500 Server Error: service inference failed")
        call_counts["single"] += 1
        return type(
            "Response",
            (),
            {"data": [{"embedding": [0.1, 0.2, 0.3]}]},
        )()

    monkeypatch.setattr(litellm, "embedding", mock_embedding)

    adapter = LiteLlmEmbeddingAdapter(
        api_key="nvapi-test",
        model="nvidia/nemotron-3.5-embed-8b",
        base_url="https://integrate.api.nvidia.com/v1",
        dimensions=3,
    )

    texts = ["Fragmento 1", "Fragmento 2", "Fragmento 3"]
    embeddings = adapter.embed_batch(texts)

    assert len(embeddings) == 3
    assert embeddings == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert call_counts["batch"] == 1
    assert call_counts["single"] == 3


@pytest.mark.unit
def test_litellm_embedding_batch_adaptive_fallback_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import litellm

    def mock_fail_all(**kwargs: object) -> object:
        raise ConnectionError("Host down")

    monkeypatch.setattr(litellm, "embedding", mock_fail_all)

    adapter = LiteLlmEmbeddingAdapter(
        api_key="nvapi-test",
        model="nvidia/nemotron-3.5-embed-8b",
        base_url="https://integrate.api.nvidia.com/v1",
        dimensions=3,
    )

    with pytest.raises(EmbeddingServiceError, match="fallback también falló"):
        adapter.embed_batch(["Texto 1", "Texto 2"])
