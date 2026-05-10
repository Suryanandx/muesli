"""Redis cache layer — optional. Falls back gracefully if Redis isn't running."""
import os
import json
from typing import Optional, Any
import redis.asyncio as aioredis

_redis: Optional[aioredis.Redis] = None

MEETINGS_LIST_KEY = "muesli:meetings:list"
MEETINGS_LIST_TTL = 60  # seconds


async def get_redis() -> Optional[aioredis.Redis]:
    global _redis
    if _redis is not None:
        return _redis
    url = os.getenv("REDIS_URL", "")
    if not url:
        return None
    try:
        client = aioredis.from_url(url, decode_responses=True, socket_timeout=2)
        await client.ping()
        _redis = client
        return _redis
    except Exception:
        return None  # Redis unavailable — degrade gracefully


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def get_cached(key: str) -> Optional[Any]:
    r = await get_redis()
    if not r:
        return None
    try:
        val = await r.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


async def set_cached(key: str, value: Any, ttl: int = 60):
    r = await get_redis()
    if not r:
        return
    try:
        await r.set(key, json.dumps(value), ex=ttl)
    except Exception:
        pass


async def invalidate(key: str):
    r = await get_redis()
    if not r:
        return
    try:
        await r.delete(key)
    except Exception:
        pass
