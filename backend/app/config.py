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
    moonshot_api_key: str
    moonshot_api_base: str = "https://api.moonshot.ai/v1"
    anthropic_api_key: str = "dummy-not-used-yet"
    openai_api_key: str = "dummy-not-used-yet"

    # Models (using OpenAI-compatible endpoint; prefix `openai/` + custom base)
    primary_model: str = "openai/kimi-k2-0905-preview"
    router_model: str = "openai/kimi-k2-0905-preview"
    embedding_model: str = "text-embedding-3-small"

    # Database (optional for Week 1-2)
    database_url: str = "sqlite+aiosqlite:///./mira.db"
    postgres_user: str = "mira"
    postgres_password: str = "mira_password"
    postgres_db: str = "mira_db"

    # Redis (optional for Week 1-2)
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant (optional for Week 1-2)
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "mira_memories"

    # Langfuse (optional - set dummy if not using)
    langfuse_public_key: str = "dummy"
    langfuse_secret_key: str = "dummy"
    langfuse_host: str = "https://cloud.langfuse.com"

    # Optional
    tavily_api_key: Optional[str] = None

    # Rate Limiting
    rate_limit_per_minute: int = 30
    rate_limit_per_day: int = 1000

    # Public v1 API keys (comma-separated). Change in production via .env.
    api_keys: str = "dev-key-change-me"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
