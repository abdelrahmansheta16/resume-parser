from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time

from app.api.schemas import JobPosting
from app.core.logging import get_logger
from app.core.paths import JOBS_DIR

logger = get_logger(__name__)

CACHE_DB_PATH = JOBS_DIR / "cache.db"
CACHE_TTL_SECONDS = 86400  # 24 hours

_local = threading.local()

_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_cache (
    cache_key TEXT PRIMARY KEY,
    connector TEXT,
    keywords TEXT,
    location TEXT,
    timestamp REAL,
    jobs TEXT
);
"""


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(CACHE_DB_PATH))
        _local.conn.row_factory = sqlite3.Row
        _local.conn.executescript(_CACHE_SCHEMA)
    return _local.conn


def _cache_key(connector: str, keywords: str, location: str) -> str:
    raw = f"{connector}:{keywords}:{location}".lower()
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached(connector: str, keywords: str, location: str) -> list[JobPosting] | None:
    """Return cached job results if fresh, else None."""
    conn = _get_conn()
    key = _cache_key(connector, keywords, location)
    row = conn.execute(
        "SELECT timestamp, jobs FROM search_cache WHERE cache_key = ?", (key,)
    ).fetchone()

    if not row:
        return None

    if time.time() - row["timestamp"] > CACHE_TTL_SECONDS:
        conn.execute("DELETE FROM search_cache WHERE cache_key = ?", (key,))
        conn.commit()
        return None

    try:
        jobs_data = json.loads(row["jobs"])
        return [JobPosting(**j) for j in jobs_data]
    except Exception as e:
        logger.warning("Cache read error for %s: %s", key, e)
        return None


def set_cache(connector: str, keywords: str, location: str, jobs: list[JobPosting]) -> None:
    """Cache job results."""
    conn = _get_conn()
    key = _cache_key(connector, keywords, location)
    jobs_json = json.dumps([j.model_dump() for j in jobs], default=str)

    conn.execute(
        """INSERT OR REPLACE INTO search_cache (cache_key, connector, keywords, location, timestamp, jobs)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (key, connector, keywords, location, time.time(), jobs_json),
    )
    conn.commit()
    logger.debug("Cached %d jobs for key %s", len(jobs), key)
