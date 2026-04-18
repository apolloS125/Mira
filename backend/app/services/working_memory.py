"""Working memory: recent conversation turns cached in Redis (1h TTL).

Also exposes a helper to load recent messages from Postgres as fallback.
"""
import json
import logging
import uuid
from typing import List

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import redis_client
from app.models.message import Message

logger = logging.getLogger(__name__)

TTL_SECONDS = 60 * 60  # 1 hour
MAX_TURNS = 20


def _key(user_id: uuid.UUID) -> str:
    return f"mira:working:{user_id}"


async def append_turn(user_id: uuid.UUID, role: str, content: str) -> None:
    """Append a message to the user's working memory list."""
    key = _key(user_id)
    try:
        await redis_client.rpush(key, json.dumps({"role": role, "content": content}))
        await redis_client.ltrim(key, -MAX_TURNS, -1)
        await redis_client.expire(key, TTL_SECONDS)
    except Exception as e:
        logger.warning(f"Redis append failed: {e}")


async def get_recent_turns(user_id: uuid.UUID, limit: int = MAX_TURNS) -> List[dict]:
    """Return recent turns as a list of {role, content} dicts."""
    key = _key(user_id)
    try:
        raw = await redis_client.lrange(key, -limit, -1)
        return [json.loads(r) for r in raw]
    except Exception as e:
        logger.warning(f"Redis read failed: {e}")
        return []


async def clear(user_id: uuid.UUID) -> None:
    try:
        await redis_client.delete(_key(user_id))
    except Exception:
        pass


async def load_recent_messages_from_db(
    session: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 10,
) -> List[dict]:
    """Fallback/short-term history from Postgres, oldest-first."""
    stmt = (
        select(Message)
        .where(Message.user_id == user_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    rows.reverse()
    return [{"role": m.role, "content": m.content} for m in rows]
