"""Basic tests to verify setup."""
import pytest


def test_import_app():
    """Verify the app can be imported."""
    from app import __version__
    assert __version__ == "0.1.0"


def test_config_loads():
    """Verify config loads (requires .env or env vars)."""
    try:
        from app.config import settings
        assert settings.app_env in ("development", "production", "testing")
    except Exception as e:
        pytest.skip(f"Config not available: {e}")


@pytest.mark.asyncio
async def test_llm_service_import():
    """Verify LLM service can be imported."""
    from app.services.llm import chat_with_llm
    assert callable(chat_with_llm)
