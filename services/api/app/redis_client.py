"""
Lazy Redis client singleton.
Initialised at startup, closed at shutdown.
"""

from __future__ import annotations

import redis.asyncio as aioredis
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)

_redis: aioredis.Redis | None = None

EVENTS_CHANNEL = "store:events"


async def init_redis() -> None:
    global _redis
    settings = get_settings()
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await _redis.ping()
        logger.info("redis_connected", url=settings.redis_url)
    except Exception as exc:
        logger.warning("redis_unavailable", error=str(exc))


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


def get_redis() -> aioredis.Redis | None:
    return _redis


async def publish_event(event_json: str) -> None:
    """Publish serialised event JSON to the store:events channel."""
    r = get_redis()
    if r:
        try:
            await r.publish(EVENTS_CHANNEL, event_json)
        except Exception as exc:
            logger.warning("redis_publish_failed", error=str(exc))
