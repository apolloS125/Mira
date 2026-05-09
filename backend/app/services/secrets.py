"""Encrypted per-user secrets vault.

Secrets are encrypted with Fernet using `settings.mira_secret_key` (a base64
urlsafe 32-byte key). The key MUST be set in production via the env var
`MIRA_SECRET_KEY`. Use `python -c "from cryptography.fernet import Fernet;
print(Fernet.generate_key().decode())"` to mint one.

Skills reference secrets by name via the `secrets` proxy injected into their
namespace (see app/skills/registry.py).
"""
from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.secret import Secret

logger = logging.getLogger(__name__)


class SecretsError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = settings.mira_secret_key
    if not key:
        raise SecretsError(
            "MIRA_SECRET_KEY is not set. Mint one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:  # noqa: BLE001
        raise SecretsError(f"MIRA_SECRET_KEY is invalid: {e}") from e


async def set_secret(user_id: uuid.UUID, name: str, value: str, scope: str = "skill") -> None:
    f = _fernet()
    blob = f.encrypt(value.encode("utf-8"))
    async with AsyncSessionLocal() as session:
        existing = (await session.execute(
            select(Secret).where(Secret.user_id == user_id, Secret.name == name)
        )).scalar_one_or_none()
        if existing is None:
            session.add(Secret(user_id=user_id, name=name, value_encrypted=blob, scope=scope))
        else:
            existing.value_encrypted = blob
            existing.scope = scope
        await session.commit()


async def get_secret(user_id: uuid.UUID, name: str) -> Optional[str]:
    f = _fernet()
    async with AsyncSessionLocal() as session:
        row = (await session.execute(
            select(Secret).where(Secret.user_id == user_id, Secret.name == name)
        )).scalar_one_or_none()
    if row is None:
        return None
    try:
        return f.decrypt(row.value_encrypted).decode("utf-8")
    except InvalidToken:
        logger.error("Secret '%s' for user %s could not be decrypted (key rotated?)", name, user_id)
        return None


async def list_secret_names(user_id: uuid.UUID) -> list[str]:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Secret.name).where(Secret.user_id == user_id)
        )).all()
    return [r[0] for r in rows]


async def delete_secret(user_id: uuid.UUID, name: str) -> bool:
    async with AsyncSessionLocal() as session:
        row = (await session.execute(
            select(Secret).where(Secret.user_id == user_id, Secret.name == name)
        )).scalar_one_or_none()
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
    return True


# Per-invocation user context. Set by the agent loop before dispatching tools
# so `secrets.get(...)` inside skills resolves to the invoking user.
_current_user_id: contextvars.ContextVar[Optional[uuid.UUID]] = contextvars.ContextVar(
    "mira_current_user_id", default=None
)


def set_current_user(user_id: uuid.UUID) -> contextvars.Token:
    return _current_user_id.set(user_id)


def reset_current_user(token: contextvars.Token) -> None:
    _current_user_id.reset(token)


class _AmbientSecretsProxy:
    """Skill-facing proxy. Reads user_id from context at call time."""

    async def get(self, name: str) -> Optional[str]:
        uid = _current_user_id.get()
        if uid is None:
            return None
        return await get_secret(uid, name)

    async def list(self) -> list[str]:
        uid = _current_user_id.get()
        if uid is None:
            return []
        return await list_secret_names(uid)


# Singleton injected into every skill's namespace.
ambient_secrets = _AmbientSecretsProxy()
