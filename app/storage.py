"""
Storage layer — PostgreSQL via asyncpg with Redis caching.
Falls back to SQLite (aiosqlite) when DATABASE_URL is not set,
so the app still works without Docker for local dev.
"""
import os
from pathlib import Path
from typing import Optional

_USE_SQLITE = not os.getenv("DATABASE_URL", "").strip()

# ── SQLite fallback (local dev without Docker) ────────────────────

_SQLITE_PATH = Path.home() / ".muesli" / "meetings.db"

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    duration    REAL    NOT NULL DEFAULT 0,
    transcript  TEXT,
    notes       TEXT    NOT NULL,
    user_notes  TEXT,
    audio_path  TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
)
"""


async def init_db():
    if _USE_SQLITE:
        import aiosqlite
        _SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(_SQLITE_PATH) as db:
            await db.execute(_SQLITE_SCHEMA)
            await db.commit()
    else:
        from app.database import init_pool
        await init_pool()


async def save_meeting(
    title: str,
    date: str,
    duration: float,
    transcript: str,
    notes: str,
    user_notes: Optional[str] = None,
    audio_path: Optional[str] = None,
) -> int:
    from app.cache import invalidate, MEETINGS_LIST_KEY
    await invalidate(MEETINGS_LIST_KEY)

    if _USE_SQLITE:
        import aiosqlite
        async with aiosqlite.connect(_SQLITE_PATH) as db:
            cur = await db.execute(
                "INSERT INTO meetings (title,date,duration,transcript,notes,user_notes,audio_path)"
                " VALUES (?,?,?,?,?,?,?)",
                (title, date, duration, transcript, notes, user_notes, audio_path),
            )
            await db.commit()
            return cur.lastrowid
    else:
        from app.database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO meetings (title,date,duration,transcript,notes,user_notes,audio_path)
                   VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id""",
                title, date, duration, transcript, notes, user_notes, audio_path,
            )
            return row["id"]


async def list_meetings() -> list[dict]:
    from app.cache import get_cached, set_cached, MEETINGS_LIST_KEY, MEETINGS_LIST_TTL
    cached = await get_cached(MEETINGS_LIST_KEY)
    if cached is not None:
        return cached

    if _USE_SQLITE:
        import aiosqlite
        async with aiosqlite.connect(_SQLITE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id,title,date,duration,created_at FROM meetings ORDER BY created_at DESC"
            )
            rows = [dict(r) for r in await cur.fetchall()]
    else:
        from app.database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT id,title,date,duration,created_at FROM meetings ORDER BY created_at DESC"
            )
            rows = [dict(r) for r in records]
        # Serialise timestamps for JSON
        for r in rows:
            if hasattr(r.get("created_at"), "isoformat"):
                r["created_at"] = r["created_at"].isoformat()

    await set_cached(MEETINGS_LIST_KEY, rows, MEETINGS_LIST_TTL)
    return rows


async def get_meeting(meeting_id: int) -> Optional[dict]:
    if _USE_SQLITE:
        import aiosqlite
        async with aiosqlite.connect(_SQLITE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,))
            row = await cur.fetchone()
            return dict(row) if row else None
    else:
        from app.database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM meetings WHERE id=$1", meeting_id)
            if not row:
                return None
            d = dict(row)
            if hasattr(d.get("created_at"), "isoformat"):
                d["created_at"] = d["created_at"].isoformat()
            return d


async def delete_meeting(meeting_id: int) -> bool:
    from app.cache import invalidate, MEETINGS_LIST_KEY
    await invalidate(MEETINGS_LIST_KEY)

    if _USE_SQLITE:
        import aiosqlite
        async with aiosqlite.connect(_SQLITE_PATH) as db:
            cur = await db.execute("DELETE FROM meetings WHERE id=?", (meeting_id,))
            await db.commit()
            return cur.rowcount > 0
    else:
        from app.database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM meetings WHERE id=$1", meeting_id)
            return result.split()[-1] != "0"
