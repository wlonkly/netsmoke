"""Tests for db.py"""

import time

import pytest
import pytest_asyncio
import aiosqlite

from netsmoke.db import (
    open_db,
    insert_samples,
    query_samples,
    query_latest_stats,
    prune_old_data,
    update_rollup,
    query_rollups,
)


@pytest_asyncio.fixture
async def db(tmp_path):
    """Provide an in-memory-like temp database."""
    path = str(tmp_path / "test.db")
    conn = await open_db(path)
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_insert_and_query(db):
    now = int(time.time())
    await insert_samples(db, "CDNs/Cloudflare", now, [10.0, 11.0, None, 12.0])

    rows = await query_samples(db, "CDNs/Cloudflare", now - 1, now + 1)
    assert len(rows) == 4

    rtts = [r[2] for r in rows]
    assert 10.0 in rtts
    assert None in rtts


@pytest.mark.asyncio
async def test_query_time_range(db):
    now = int(time.time())
    await insert_samples(db, "target", now - 100, [5.0])
    await insert_samples(db, "target", now, [10.0])
    await insert_samples(db, "target", now + 100, [15.0])

    rows = await query_samples(db, "target", now - 50, now + 50)
    assert len(rows) == 1
    assert rows[0][2] == 10.0


@pytest.mark.asyncio
async def test_query_target_isolation(db):
    now = int(time.time())
    await insert_samples(db, "target_a", now, [1.0, 2.0])
    await insert_samples(db, "target_b", now, [3.0, 4.0])

    rows_a = await query_samples(db, "target_a", now - 1, now + 1)
    assert len(rows_a) == 2
    assert all(r[2] in (1.0, 2.0) for r in rows_a)


@pytest.mark.asyncio
async def test_query_latest_stats_no_data(db):
    stats = await query_latest_stats(db, "nonexistent", window_seconds=300)
    assert stats["median_ms"] is None
    assert stats["loss_pct"] is None
    assert stats["sample_count"] == 0


@pytest.mark.asyncio
async def test_query_latest_stats_with_data(db):
    now = int(time.time())
    await insert_samples(db, "tgt", now, [10.0, 20.0, 30.0, None])

    stats = await query_latest_stats(db, "tgt", window_seconds=60)
    assert stats["sample_count"] == 4
    assert stats["loss_pct"] == 25.0
    assert stats["median_ms"] == pytest.approx(20.0, abs=1.0)


@pytest.mark.asyncio
async def test_prune_old_data(db):
    now = int(time.time())
    old_ts = now - (400 * 86400)  # 400 days ago
    await insert_samples(db, "tgt", old_ts, [1.0, 2.0])
    await insert_samples(db, "tgt", now, [3.0, 4.0])

    deleted = await prune_old_data(db, days=365)
    assert deleted == 2

    rows = await query_samples(db, "tgt", 0, now + 1)
    assert len(rows) == 2
    assert all(r[2] in (3.0, 4.0) for r in rows)


@pytest.mark.asyncio
async def test_sample_ordering(db):
    now = int(time.time())
    # Insert out of order
    await insert_samples(db, "tgt", now + 60, [20.0])
    await insert_samples(db, "tgt", now, [10.0])

    rows = await query_samples(db, "tgt", now - 1, now + 120)
    times = [r[0] for r in rows]
    assert times == sorted(times)


# --- Rollup tests ---

@pytest.mark.asyncio
async def test_update_rollup_creates_row(db):
    now = int(time.time())
    await insert_samples(db, "tgt", now, [10.0, 20.0, None, 30.0])
    await update_rollup(db, "tgt", now, "hour", 20)

    bucket_start = (now // 3600) * 3600
    rows = await query_rollups(db, "tgt", bucket_start, bucket_start + 3600, "hour")
    assert len(rows) == 1
    row = rows[0]
    assert row["bucket_start"] == bucket_start
    assert row["total_count"] == 4
    assert row["loss_count"] == 1
    assert sorted(row["sorted_rtts"]) == row["sorted_rtts"]
    assert set(row["sorted_rtts"]) == {10.0, 20.0, 30.0}


@pytest.mark.asyncio
async def test_update_rollup_idempotent(db):
    now = int(time.time())
    await insert_samples(db, "tgt", now, [10.0, 20.0])
    await update_rollup(db, "tgt", now, "hour", 20)
    # Second call updates the same row — still one row
    await update_rollup(db, "tgt", now, "hour", 20)

    bucket_start = (now // 3600) * 3600
    rows = await query_rollups(db, "tgt", bucket_start, bucket_start + 3600, "hour")
    assert len(rows) == 1
    assert rows[0]["total_count"] == 2


@pytest.mark.asyncio
async def test_update_rollup_subsamples(db):
    now = int(time.time())
    # Insert more RTTs than pings limit
    rtts = [float(i) for i in range(50)]
    await insert_samples(db, "tgt", now, rtts)
    await update_rollup(db, "tgt", now, "hour", pings=10)

    bucket_start = (now // 3600) * 3600
    rows = await query_rollups(db, "tgt", bucket_start, bucket_start + 3600, "hour")
    assert len(rows) == 1
    assert len(rows[0]["sorted_rtts"]) == 10


@pytest.mark.asyncio
async def test_query_rollups_range(db):
    # Insert samples across two different hours
    hour = 3600
    base = (int(time.time()) // hour) * hour
    ts_h0 = base - 2 * hour + 10
    ts_h1 = base - 1 * hour + 10
    ts_h2 = base + 10

    await insert_samples(db, "tgt", ts_h0, [1.0])
    await update_rollup(db, "tgt", ts_h0, "hour", 20)

    await insert_samples(db, "tgt", ts_h1, [2.0])
    await update_rollup(db, "tgt", ts_h1, "hour", 20)

    await insert_samples(db, "tgt", ts_h2, [3.0])
    await update_rollup(db, "tgt", ts_h2, "hour", 20)

    # Query only the middle two buckets
    bucket_h1 = (ts_h1 // hour) * hour
    bucket_h2 = (ts_h2 // hour) * hour
    rows = await query_rollups(db, "tgt", bucket_h1, bucket_h2, "hour")
    assert len(rows) == 2
    bucket_starts = [r["bucket_start"] for r in rows]
    assert bucket_starts == sorted(bucket_starts)
