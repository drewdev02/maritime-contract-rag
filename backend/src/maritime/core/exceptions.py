"""Core domain exceptions for the Maritime Contract RAG system."""

from typing import ClassVar


class DomainError(Exception):
    """Base exception for all domain business errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EventDecodeError(DomainError):
    """Raised when an event envelope or its payload cannot be read."""

    pass


class EntityNotFoundError(DomainError):
    """Raised when a domain entity cannot be found by its identity."""

    def __init__(self, entity_name: str, entity_id: str) -> None:
        self.entity_name = entity_name
        self.entity_id = entity_id
        super().__init__(f"{entity_name} with identity '{entity_id}' was not found.")


class InvariantViolationError(DomainError):
    """Raised when an operation would violate an entity or aggregate invariant."""

    pass


class InvalidStateTransitionError(InvariantViolationError):
    """Raised when an aggregate cannot transition from its current state to a target state."""

    def __init__(self, entity_name: str, current_state: str, target_state: str) -> None:
        self.entity_name = entity_name
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(
            f"Cannot transition {entity_name} from state '{current_state}' to '{target_state}'."
        )


class ConflictError(DomainError):
    """Raised when a domain action conflicts with existing data (e.g. duplicate hash)."""

    pass


class UnverifiedCitationError(DomainError):
    """Raised when an LLM citation fails cross-validation against retrieved chunks."""

    pass


class InsufficientEvidenceError(DomainError):
    """Raised when the document context lacks sufficient evidence to answer the query."""

    pass


class CorruptedPdfError(DomainError):
    """Raised when a PDF file is empty, malformed or cannot be parsed."""

    def __init__(self, message: str = "Archivo corrupto o sin páginas legibles") -> None:
        super().__init__(message)


class PasswordProtectedPdfError(DomainError):
    """Raised when a PDF file is encrypted or password-protected."""

    def __init__(self, message: str = "El documento está protegido por contraseña") -> None:
        super().__init__(message)


class EmptyDocumentChunksError(DomainError):
    """Raised when document extraction or chunking produces zero valid text fragments."""

    def __init__(
        self, message: str = "No se pudieron extraer fragmentos válidos del documento."
    ) -> None:
        super().__init__(message)


class ProviderError(DomainError):
    """Raised when an external AI provider (LLM or embeddings) cannot serve a request.

    ``kind`` is one of ``unavailable`` (timeout, connection or 5xx), ``quota`` (rate limit or
    exhausted quota) or ``malformed`` (the response could not be parsed or validated).
    """

    SERVICE = "proveedor de IA"
    HTTP_STATUS: ClassVar[dict[str, int]] = {"unavailable": 503, "quota": 429, "malformed": 502}

    def __init__(self, message: str, kind: str = "unavailable") -> None:
        self.kind = kind if kind in self.HTTP_STATUS else "unavailable"
        super().__init__(message)

    @property
    def http_status(self) -> int:
        return self.HTTP_STATUS[self.kind]

    @property
    def user_message(self) -> str:
        """Readable, content-free explanation that is safe to show to end users."""
        if self.kind == "quota":
            return f"El {self.SERVICE} alcanzó su límite de uso. Intenta de nuevo en unos minutos."
        if self.kind == "malformed":
            return f"El {self.SERVICE} devolvió una respuesta inválida. Intenta de nuevo."
        return f"El {self.SERVICE} no está disponible en este momento. Intenta de nuevo más tarde."


class EmbeddingServiceError(ProviderError):
    """Raised when the embedding service fails or lacks required configuration."""

    SERVICE = "servicio de embeddings"

    def __init__(self, message: str, model: str | None = None, kind: str = "unavailable") -> None:
        self.model = model
        detail = f" ({model})" if model else ""
        super().__init__(f"Error en el servicio de embeddings{detail}: {message}", kind=kind)


class LlmServiceError(ProviderError):
    """Raised when the LLM provider fails after retries."""

    SERVICE = "modelo de lenguaje"

    def __init__(self, message: str, kind: str = "unavailable") -> None:
        super().__init__(f"Error en el modelo de lenguaje: {message}", kind=kind)


def classify_provider_failure(exc: BaseException) -> str:
    """Maps any provider SDK exception to ``unavailable``, ``quota`` or ``malformed``.

    Works on class names and ``status_code`` so the core stays free of SDK imports.
    """
    names = " ".join(c.__name__ for c in type(exc).__mro__)
    text = str(exc).lower()
    status = getattr(exc, "status_code", None)
    if status == 429 or "RateLimit" in names or "resource_exhausted" in text or "quota" in text:
        return "quota"
    if (
        "UnexpectedModelBehavior" in names
        or "ValidationError" in names
        or "JSONDecodeError" in names
        or "malformed" in text
    ):
        return "malformed"
    return "unavailable"
