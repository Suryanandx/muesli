"""PostgreSQL connection pool — created once at startup, shared across requests."""
import os
from typing import Optional
import asyncpg

_pool: Optional[asyncpg.Pool] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id          SERIAL PRIMARY KEY,
    title       TEXT        NOT NULL,
    date        TEXT        NOT NULL,
    duration    REAL        NOT NULL DEFAULT 0,
    transcript  TEXT,
    notes       TEXT        NOT NULL,
    user_notes  TEXT,
    audio_path  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS meetings_created_at_idx ON meetings (created_at DESC);
"""


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set. Add it to .env or start via docker compose."
        )
    _pool = await asyncpg.create_pool(
        url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)
    return _pool


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        return await init_pool()
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
