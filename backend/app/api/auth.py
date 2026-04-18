"""API key auth — minimal dependency for public v1 endpoints.

Keys live in settings.api_keys (comma-separated). Clients pass them via
`X-API-Key` header. For local dev, a default key is accepted.
"""
from fastapi import Header, HTTPException, status

from app.config import settings


def _parse_keys(raw: str) -> set[str]:
    return {k.strip() for k in raw.split(",") if k.strip()}


async def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    allowed = _parse_keys(settings.api_keys)
    if not x_api_key or x_api_key not in allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid X-API-Key",
        )
    return x_api_key
