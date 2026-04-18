"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    debug: bool = True
    base_url: str = "http://localhost:8000"
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"

    # Telegram
    telegram_bot_token: str
    telegram_webhook_secret: str = ""

    # LLM Providers
    anthropic_api_key: str
    openai_api_key: str

    # Models
    primary_model: str = "claude-opus-4-7"
    router_model: str = "claude-haiku-4-5"
    embedding_model: str = "text-embedding-3-small"

    # Database
    database_url: str
    postgres_user: str = "mira"
    postgres_password: str = "mira_password"
    postgres_db: str = "mira_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "mira_memories"

    # Langfuse
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str = "https://cloud.langfuse.com"

    # Optional
    tavily_api_key: Optional[str] = None

    # Rate Limiting
    rate_limit_per_minute: int = 30
    rate_limit_per_day: int = 1000


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
