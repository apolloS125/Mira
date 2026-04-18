"""Redis client for working memory and caching."""
import logging

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


# Global Redis client
redis_client: redis.Redis = redis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis() -> redis.Redis:
    """Dependency to get Redis client."""
    return redis_client


async def close_redis() -> None:
    """Close Redis connections."""
    await redis_client.aclose()
    logger.info("👋 Redis connections closed")
