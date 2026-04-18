"""Pytest configuration."""
import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio for anyio tests."""
    return "asyncio"
