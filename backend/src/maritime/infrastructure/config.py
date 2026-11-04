from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded strictly from environment variables with safe defaults."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = Field(
        default="development",
        description="Application environment: development, test, production",
    )

    # Agnostic LLM Settings
    LLM_PROVIDER: str = Field(
        default="mock",
        description="LLM provider: 'mock', 'gemini', or 'openai'",
    )
    LLM_API_KEY: str = Field(
        default="",
        description="API Key for the LLM provider",
    )
    LLM_MODEL: str = Field(
        default="gemini-1.5-flash",
        description="Generative LLM model name",
    )
    LLM_BASE_URL: str | None = Field(
        default=None,
        description="Custom base URL for the LLM provider (optional)",
    )
    LLM_TIMEOUT: float = Field(
        default=30.0,
        description="Timeout in seconds for LLM calls",
    )

    # Agnostic Embedding Settings (Separated URL & Model)
    EMBEDDING_PROVIDER: str = Field(
        default="mock",
        description="Embedding provider: 'mock', 'gemini', 'openai'",
    )
    EMBEDDING_API_KEY: str = Field(
        default="",
        description="API Key for the embedding provider",
    )
    EMBEDDING_MODEL: str = Field(
        default="gemini/text-embedding-004",
        description="Embedding model name",
    )
    EMBEDDING_BASE_URL: str | None = Field(
        default=None,
        description="Independent custom base URL for the embedding service (optional)",
    )
    EMBEDDING_TIMEOUT: float = Field(
        default=30.0,
        description="Timeout in seconds for each embedding request",
    )
    EMBEDDING_MAX_RETRIES: int = Field(
        default=3,
        description="Retries with exponential backoff on transient embedding errors",
    )
    EMBEDDING_DIMENSIONS: int = Field(
        default=768,
        description="Target embedding vector dimension",
    )

    # CORS Settings
    CORS_ORIGINS: str = Field(
        default="*",
        description="Allowed CORS origins as comma-separated string (e.g. '*' or 'http://localhost:3000,http://localhost:3005')",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parses CORS_ORIGINS string into a list of origins."""
        return [i.strip() for i in self.CORS_ORIGINS.split(",") if i.strip()]

    # Database & Cache
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgrespassword@localhost:5432/maritime_rag",
        description="Async SQLAlchemy database URL",
    )
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker URL",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        description="Celery result backend URL",
    )

    # Domain event stream (Redis Streams, shared by the API and the worker)
    EVENT_BUS_BACKEND: str = Field(
        default="memory",
        description="'redis' to publish events across processes, 'memory' to keep them in-process",
    )
    EVENT_REDIS_URL: str = Field(
        default="redis://localhost:6379/2",
        description="Redis database holding the event stream (separate from the Celery ones)",
    )
    EVENT_STREAM_KEY: str = Field(
        default="maritime:events",
        description="Redis key of the domain event stream",
    )
    EVENT_STREAM_MAXLEN: int = Field(
        default=10_000,
        description="Maximum number of events kept in the stream (oldest are trimmed)",
    )

    # Storage
    STORAGE_PATH: str = Field(
        default="/app/storage/contracts",
        description="Directory for local PDF storage",
    )
    MAX_FILE_SIZE_BYTES: int = Field(
        default=26_214_400,
        description="Maximum PDF file size in bytes",
    )

    # RAG & Indexing Hyperparameters
    CHUNK_MAX_CHARS: int = Field(
        default=500,
        description="Maximum characters per chunk",
    )
    CHUNK_OVERLAP_CHARS: int = Field(
        default=80,
        description="Overlap characters between chunks",
    )
    PROCESSING_TIMEOUT_SECONDS: int = Field(
        default=900,
        description="A document in PROCESSING longer than this is marked FAILED by the reaper",
    )
    TASK_VISIBILITY_TIMEOUT_SECONDS: int = Field(
        default=600,
        description="Redis redelivery timeout for unacknowledged tasks (must exceed task time)",
    )
    RAG_SIMILARITY_THRESHOLD: float = Field(
        default=0.25,
        description="Minimum cosine similarity threshold to provide an answer",
    )
    RAG_TOP_K: int = Field(
        default=5,
        description="Default top-k chunks to retrieve for RAG",
    )

    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: str = Field(
        default="http://localhost:4318",
        description="OpenTelemetry OTLP collector endpoint",
    )
    OTEL_TRACES_EXPORTER: str = Field(
        default="none",
        description="Trace exporter: 'otlp' (OTLP/HTTP), 'console' or 'none'",
    )
    OTEL_SERVICE_NAME: str = Field(
        default="maritime-api",
        description="OpenTelemetry service name",
    )


settings = Settings()
