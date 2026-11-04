import logging
from collections.abc import Sequence
from typing import Any

import litellm

from maritime.core.exceptions import EmbeddingServiceError, classify_provider_failure
from maritime.modules.indexing.domain.ports import IEmbeddingService

logger = logging.getLogger(__name__)


class LiteLlmEmbeddingAdapter(IEmbeddingService):
    """Agnostic embedding adapter using LiteLLM (supports Gemini, OpenAI, Ollama, custom URLs)."""

    def __init__(
        self,
        api_key: str | None,
        model: str,
        base_url: str | None,
        dimensions: int | None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not api_key and not base_url:
            raise EmbeddingServiceError(
                message="Se requiere API key o base_url configurada para el servicio.",
                model=model,
            )

        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.dimensions = dimensions
        self.timeout = timeout
        self.max_retries = max_retries

    def _prepare_kwargs(self, input_type: str | None = None) -> dict[str, Any]:
        # LiteLLM applies its own exponential backoff for ``num_retries`` on transient errors.
        kwargs: dict[str, Any] = {
            "model": self.model,
            "timeout": self.timeout,
            "num_retries": self.max_retries,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["api_base"] = self.base_url

        is_nvidia = "nvidia" in self.model.lower() or "nemotron" in self.model.lower()
        if is_nvidia:
            if self.model.startswith("openai/"):
                extra: dict[str, Any] = {}
                if input_type:
                    extra["input_type"] = input_type
                if self.dimensions:
                    extra["dimensions"] = self.dimensions
                if extra:
                    kwargs["extra_body"] = extra
            else:
                if input_type:
                    kwargs["input_type"] = input_type
                if self.dimensions:
                    kwargs["dimensions"] = self.dimensions
        elif self.dimensions and ("text-embedding-3" in self.model):
            kwargs["dimensions"] = self.dimensions

        return kwargs

    def _embed_single(self, text: str, input_type: str) -> list[float]:
        kwargs = self._prepare_kwargs(input_type=input_type)
        kwargs["input"] = [text]
        response = litellm.embedding(**kwargs)
        data = response.data[0]["embedding"]
        return [float(x) for x in data]

    def embed_text(self, text: str) -> list[float]:
        try:
            return self._embed_single(text, input_type="query")
        except Exception as e:
            raise EmbeddingServiceError(
                message=f"Error durante la generación de embedding: {e}",
                model=self.model,
                kind=classify_provider_failure(e),
            ) from e

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        if len(texts) == 1:
            try:
                return [self._embed_single(texts[0], input_type="passage")]
            except Exception as e:
                raise EmbeddingServiceError(
                    message=f"Error durante la generación de embedding: {e}",
                    model=self.model,
                    kind=classify_provider_failure(e),
                ) from e

        try:
            kwargs = self._prepare_kwargs(input_type="passage")
            kwargs["input"] = list(texts)
            response = litellm.embedding(**kwargs)
            return [[float(x) for x in item["embedding"]] for item in response.data]
        except Exception as batch_error:
            logger.warning(
                "Llamada en lote a embeddings falló para el modelo %s (%s). "
                "Activando fallback adaptativo uno a uno.",
                self.model,
                batch_error,
            )
            try:
                return [self._embed_single(text, input_type="passage") for text in texts]
            except Exception as fallback_error:
                raise EmbeddingServiceError(
                    message=(
                        f"Error durante la generación de embeddings en lote (fallback también falló): {fallback_error}"
                    ),
                    model=self.model,
                    kind=classify_provider_failure(fallback_error),
                ) from fallback_error
