"""
SQLite database schema, connection helpers, and query utilities.

Schema is designed to be compatible with future migration to PostgreSQL + TimescaleDB.
"""

from __future__ import annotations

import json
import time
from typing import Optional

import aiosqlite


# DDL
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ping_samples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    time        INTEGER NOT NULL,   -- Unix timestamp (seconds)
    target      TEXT NOT NULL,      -- e.g. "CDNs/Cloudflare"
    sample_num  INTEGER NOT NULL,   -- 1..N
    rtt_ms      REAL                -- NULL = packet loss
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_ping_samples_target_time
    ON ping_samples (target, time);
"""

CREATE_ROLLUP_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ping_rollups (
    id           INTEGER PRIMARY KEY,
    target       TEXT NOT NULL,
    bucket_start INTEGER NOT NULL,
    bucket_size  TEXT NOT NULL,        -- "hour" or "day"
    sorted_rtts  TEXT NOT NULL,        -- JSON array, pre-sorted, non-null only
    loss_count   INTEGER NOT NULL,
    total_count  INTEGER NOT NULL,
    UNIQUE (target, bucket_start, bucket_size)
);
"""

CREATE_ROLLUP_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_ping_rollups_target_bucket
    ON ping_rollups (target, bucket_start, bucket_size);
"""

_BUCKET_DURATIONS = {
    "hour": 3600,
    "day":  86400,
}


async def init_db(db: aiosqlite.Connection) -> None:
    """Create tables and indexes if they don't exist."""
    await db.execute(CREATE_TABLE_SQL)
    await db.execute(CREATE_INDEX_SQL)
    await db.execute(CREATE_ROLLUP_TABLE_SQL)
    await db.execute(CREATE_ROLLUP_INDEX_SQL)
    await db.commit()


async def open_db(path: str) -> aiosqlite.Connection:
    """Open a database connection and initialize schema."""
    db = await aiosqlite.connect(path)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    await init_db(db)
    return db


async def insert_samples(
    db: aiosqlite.Connection,
    target: str,
    timestamp: int,
    rtts: list[Optional[float]],
) -> None:
    """
    Insert a batch of ping samples for a single target at a single timestamp.

    rtts: list of RTT values in ms, None for packet loss.
    """
    rows = [
        (timestamp, target, i + 1, rtt)
        for i, rtt in enumerate(rtts)
    ]
    await db.executemany(
        "INSERT INTO ping_samples (time, target, sample_num, rtt_ms) VALUES (?, ?, ?, ?)",
        rows,
    )
    await db.commit()


async def query_samples(
    db: aiosqlite.Connection,
    target: str,
    start: int,
    end: int,
) -> list[tuple[int, int, Optional[float]]]:
    """
    Return all samples for a target in [start, end] time range.

    Returns list of (time, sample_num, rtt_ms) tuples, ordered by time, sample_num.
    """
    async with db.execute(
        """
        SELECT time, sample_num, rtt_ms
        FROM ping_samples
        WHERE target = ? AND time >= ? AND time <= ?
        ORDER BY time, sample_num
        """,
        (target, start, end),
    ) as cursor:
        rows = await cursor.fetchall()
    return [(int(r[0]), int(r[1]), r[2]) for r in rows]


async def query_latest_stats(
    db: aiosqlite.Connection,
    target: str,
    window_seconds: int = 300,
) -> dict:
    """
    Return recent median RTT and packet loss % for a target.

    Looks at the most recent `window_seconds` of data.
    """
    end = int(time.time())
    start = end - window_seconds

    rows = await query_samples(db, target, start, end)
    if not rows:
        return {"median_ms": None, "loss_pct": None, "sample_count": 0}

    rtts = [r[2] for r in rows]
    total = len(rtts)
    received = [r for r in rtts if r is not None]
    loss_pct = (total - len(received)) / total * 100 if total > 0 else 0.0

    if received:
        sorted_r = sorted(received)
        n = len(sorted_r)
        if n % 2 == 0:
            median_ms = (sorted_r[n // 2 - 1] + sorted_r[n // 2]) / 2
        else:
            median_ms = sorted_r[n // 2]
    else:
        median_ms = None

    return {
        "median_ms": median_ms,
        "loss_pct": round(loss_pct, 1),
        "sample_count": total,
    }


async def prune_old_data(db: aiosqlite.Connection, days: int = 365) -> int:
    """Delete samples older than `days` days. Returns number of rows deleted."""
    cutoff = int(time.time()) - days * 86400
    cursor = await db.execute(
        "DELETE FROM ping_samples WHERE time < ?",
        (cutoff,),
    )
    await db.commit()
    return cursor.rowcount


async def update_rollup(
    db: aiosqlite.Connection,
    target: str,
    probe_timestamp: int,
    bucket_size: str,
    pings: int,
) -> None:
    """
    Compute and upsert a rollup row for the bucket containing probe_timestamp.

    bucket_size: "hour" or "day"
    pings: maximum number of RTT values to store in sorted_rtts
    """
    duration = _BUCKET_DURATIONS[bucket_size]
    bucket_start = (probe_timestamp // duration) * duration
    bucket_end = bucket_start + duration

    rows = await query_samples(db, target, bucket_start, bucket_end - 1)
    all_rtts = [r[2] for r in rows]
    total_count = len(all_rtts)
    received = sorted(r for r in all_rtts if r is not None)
    loss_count = total_count - len(received)

    # Sub-sample to at most `pings` values using evenly-spaced indices
    if len(received) > pings:
        if pings == 1:
            received = [received[len(received) // 2]]
        else:
            indices = [round(i * (len(received) - 1) / (pings - 1)) for i in range(pings)]
            received = [received[i] for i in indices]

    await db.execute(
        """
        INSERT INTO ping_rollups (target, bucket_start, bucket_size, sorted_rtts, loss_count, total_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (target, bucket_start, bucket_size) DO UPDATE SET
            sorted_rtts = excluded.sorted_rtts,
            loss_count  = excluded.loss_count,
            total_count = excluded.total_count
        """,
        (target, bucket_start, bucket_size, json.dumps(received), loss_count, total_count),
    )
    await db.commit()


async def query_rollups(
    db: aiosqlite.Connection,
    target: str,
    start: int,
    end: int,
    bucket_size: str,
) -> list[dict]:
    """
    Return rollup rows for a target in [start, end] time range.

    Returns list of dicts:
        {"bucket_start": int, "sorted_rtts": list[float], "loss_count": int, "total_count": int}
    """
    async with db.execute(
        """
        SELECT bucket_start, sorted_rtts, loss_count, total_count
        FROM ping_rollups
        WHERE target = ? AND bucket_size = ? AND bucket_start >= ? AND bucket_start <= ?
        ORDER BY bucket_start
        """,
        (target, bucket_size, start, end),
    ) as cursor:
        rows = await cursor.fetchall()
    return [
        {
            "bucket_start": int(r[0]),
            "sorted_rtts": json.loads(r[1]),
            "loss_count": int(r[2]),
            "total_count": int(r[3]),
        }
        for r in rows
    ]
