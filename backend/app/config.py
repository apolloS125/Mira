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
    # Single-owner mode: only this Telegram ID can interact with the bot.
    # Default 0 = fail closed (rejects everyone). Must be set explicitly to enable bot.
    owner_telegram_id: int = 0

    # LLM Providers
    moonshot_api_key: str
    moonshot_api_base: str = "https://api.moonshot.ai/v1"
    # If set, send LLM requests through the local LiteLLM proxy using this key
    # (proxy master key or virtual key) instead of moonshot_api_key. Leave empty
    # to call Moonshot directly.
    litellm_proxy_key: str = ""
    anthropic_api_key: str = "dummy-not-used-yet"
    openai_api_key: str = "dummy-not-used-yet"

    # Models (using OpenAI-compatible endpoint; prefix `openai/` + custom base)
    primary_model: str = "openai/kimi-k2.5"
    router_model: str = "openai/kimi-k2.5"
    embedding_model: str = "text-embedding-3-small"

    # Database
    database_url: str = "sqlite+aiosqlite:///./mira.db"

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

    # Skill sandbox
    mira_secret_key: str = ""  # Fernet base64 key for secrets vault. Required at startup.
    skill_run_timeout_sec: int = 15
    skill_max_output_bytes: int = 32_768


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
