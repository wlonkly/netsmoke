"""
Core import logic: initialise the DB and bulk-insert RRD data.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from netsmoke.db import (
    CREATE_INDEX_SQL,
    CREATE_ROLLUP_INDEX_SQL,
    CREATE_ROLLUP_TABLE_SQL,
    CREATE_TABLE_SQL,
)

from .rrd_parser import RRDMeta, dump_rrd, iter_rows_finest_first, parse_rrd_header

if TYPE_CHECKING:
    pass

BATCH_SIZE = 50_000

# Pragmas tuned for bulk writes (one-time import)
_IMPORT_PRAGMAS = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=OFF",
    "PRAGMA cache_size=-65536",  # 64 MB
    "PRAGMA temp_store=MEMORY",
]


def open_db(db_path: str) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    for pragma in _IMPORT_PRAGMAS:
        db.execute(pragma)
    db.execute(CREATE_TABLE_SQL)
    db.execute(CREATE_INDEX_SQL)
    db.execute(CREATE_ROLLUP_TABLE_SQL)
    db.execute(CREATE_ROLLUP_INDEX_SQL)
    db.commit()
    return db


def _insert_batch(db: sqlite3.Connection, rows: list[tuple]) -> None:
    db.execute("BEGIN")
    db.executemany(
        "INSERT INTO ping_samples (time, target, sample_num, rtt_ms) VALUES (?,?,?,?)",
        rows,
    )
    db.execute("COMMIT")


def import_rrd(
    db: sqlite3.Connection,
    rrd_path: str,
    target_path: str,
    dry_run: bool = False,
) -> dict:
    """
    Import a single RRD file into the DB.

    target_path: e.g. "Internet/google"
    Returns a stats dict with counts per archive and totals.
    """
    lines = dump_rrd(rrd_path)
    meta: RRDMeta = parse_rrd_header(lines)

    if meta.ping_count == 0:
        return {"target": target_path, "skipped": True, "reason": "no ping DS found"}

    # Per-archive stats for progress output
    from .rrd_parser import iter_rra_rows  # local import to avoid circular
    average_rras = sorted(meta.average_rras(), key=lambda r: r.step_seconds)

    seen: set[int] = set()
    archive_stats: list[dict] = []
    all_rows: list[tuple] = []

    min_ts: int | None = None
    max_ts: int | None = None

    for rra in average_rras:
        rra_rows = list(iter_rra_rows(lines, rra.index, meta))
        new_ts = [ts for ts, _ in rra_rows if ts not in seen]
        archive_stats.append({
            "step": rra.step_seconds,
            "total": len(rra_rows),
            "new": len(new_ts),
        })

        for ts, ping_values in rra_rows:
            if ts in seen:
                continue
            seen.add(ts)
            if min_ts is None or ts < min_ts:
                min_ts = ts
            if max_ts is None or ts > max_ts:
                max_ts = ts
            for i, val in enumerate(ping_values):
                rtt_ms = val * 1000.0 if val is not None else None
                all_rows.append((ts, target_path, i + 1, rtt_ms))

    if not dry_run and all_rows:
        for offset in range(0, len(all_rows), BATCH_SIZE):
            _insert_batch(db, all_rows[offset: offset + BATCH_SIZE])

    def _fmt_ts(ts: int | None) -> str:
        if ts is None:
            return "?"
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

    return {
        "target": target_path,
        "archive_stats": archive_stats,
        "total_timestamps": len(seen),
        "total_rows": len(all_rows),
        "start_date": _fmt_ts(min_ts),
        "end_date": _fmt_ts(max_ts),
        "dry_run": dry_run,
    }


def backfill_rollups(db: sqlite3.Connection, ping_count: int) -> dict:
    """
    Compute rollup rows for all data in ping_samples.

    Iterates over every target, groups samples into hour and day buckets,
    sub-samples to ping_count values, and upserts into ping_rollups.
    Returns a stats dict with bucket counts per size.
    """
    import json

    targets = [
        r[0] for r in db.execute("SELECT DISTINCT target FROM ping_samples").fetchall()
    ]

    total_hour = 0
    total_day = 0

    for target in targets:
        for bucket_size, duration in [("hour", 3600), ("day", 86400)]:
            # Fetch all rows for this target sorted by bucket then RTT.
            # In SQLite, ORDER BY rtt_ms ASC puts NULLs first, so filtering
            # them out leaves the non-null values already in ascending order.
            rows = db.execute(
                """
                SELECT (time / ?) * ? AS bucket_start, rtt_ms
                FROM ping_samples
                WHERE target = ?
                ORDER BY bucket_start, rtt_ms
                """,
                (duration, duration, target),
            ).fetchall()

            # Group by bucket_start
            buckets: dict[int, list] = {}
            for bucket_start, rtt_ms in rows:
                buckets.setdefault(bucket_start, []).append(rtt_ms)

            batch = []
            for bucket_start, rtts in sorted(buckets.items()):
                total_count = len(rtts)
                received = [r for r in rtts if r is not None]
                loss_count = total_count - len(received)

                if len(received) > ping_count:
                    if ping_count == 1:
                        received = [received[len(received) // 2]]
                    else:
                        indices = [
                            round(i * (len(received) - 1) / (ping_count - 1))
                            for i in range(ping_count)
                        ]
                        received = [received[i] for i in indices]

                batch.append((
                    target, bucket_start, bucket_size,
                    json.dumps(received), loss_count, total_count,
                ))

            if batch:
                db.executemany(
                    """
                    INSERT INTO ping_rollups
                        (target, bucket_start, bucket_size, sorted_rtts, loss_count, total_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (target, bucket_start, bucket_size) DO UPDATE SET
                        sorted_rtts = excluded.sorted_rtts,
                        loss_count  = excluded.loss_count,
                        total_count = excluded.total_count
                    """,
                    batch,
                )
                db.commit()

                if bucket_size == "hour":
                    total_hour += len(batch)
                else:
                    total_day += len(batch)

    return {
        "targets": len(targets),
        "hour_buckets": total_hour,
        "day_buckets": total_day,
    }


def find_rrd_files(data_dir: str) -> list[tuple[str, str]]:
    """
    Walk data_dir recursively, returning (rrd_path, target_path) pairs.

    target_path strips the data_dir prefix and .rrd suffix, then
    joins with "/" to produce e.g. "Internet/google".
    """
    base = Path(data_dir).resolve()
    results: list[tuple[str, str]] = []
    for rrd in sorted(base.rglob("*.rrd")):
        rel = rrd.relative_to(base).with_suffix("")
        target_path = "/".join(rel.parts)
        results.append((str(rrd), target_path))
    return results
