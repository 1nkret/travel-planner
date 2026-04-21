import json
from typing import Any

from redis.asyncio import Redis, from_url

from app.config import settings


_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def cache_get(key: str) -> Any | None:
    raw = await get_redis().get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # drop the bad key rather than blow up the whole request
        await get_redis().delete(key)
        return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    await get_redis().set(key, json.dumps(value), ex=ttl)
