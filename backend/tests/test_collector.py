"""Tests for collector.py"""

import time

import pytest
import pytest_asyncio

from netsmoke.collector import _collect_once
from netsmoke.config import Config, Target
from netsmoke.db import open_db, query_samples


def _make_config(host="127.0.0.1", name="Test", ping_count=3, ping_interval=60):
    target = Target(name=name, host=host, folder_path="")
    return Config(
        ping_count=ping_count,
        ping_interval=ping_interval,
        all_targets=[target],
        tree=[target],
    )


@pytest_asyncio.fixture
async def db(tmp_path):
    conn = await open_db(str(tmp_path / "collector_test.db"))
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_collect_once_stores_samples(db, monkeypatch):
    """_collect_once writes one row per ping for each target."""
    config = _make_config(host="8.8.8.8", name="Google DNS", ping_count=3)

    async def mock_ping(hosts, **kwargs):
        return {"8.8.8.8": [10.0, 11.0, 12.0]}

    monkeypatch.setattr("netsmoke.collector.ping_hosts", mock_ping)

    before = int(time.time())
    await _collect_once(config, db)
    after = int(time.time())

    rows = await query_samples(db, "Google DNS", before - 1, after + 1)
    assert len(rows) == 3
    assert sorted(r[2] for r in rows) == [10.0, 11.0, 12.0]


@pytest.mark.asyncio
async def test_collect_once_no_targets(db, monkeypatch):
    """_collect_once returns immediately without calling ping_hosts when there are no targets."""
    config = Config(ping_count=5, ping_interval=60, all_targets=[], tree=[])

    called = False

    async def mock_ping(hosts, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr("netsmoke.collector.ping_hosts", mock_ping)

    await _collect_once(config, db)
    assert not called


@pytest.mark.asyncio
async def test_collect_once_ping_failure_is_swallowed(db, monkeypatch):
    """A RuntimeError from ping_hosts is logged but does not propagate."""
    config = _make_config(ping_count=3)

    async def mock_ping(hosts, **kwargs):
        raise RuntimeError("fping not found")

    monkeypatch.setattr("netsmoke.collector.ping_hosts", mock_ping)

    before = int(time.time())
    await _collect_once(config, db)  # must not raise

    rows = await query_samples(db, "Test", before - 1, int(time.time()) + 1)
    assert rows == []


@pytest.mark.asyncio
async def test_collect_once_all_loss_stored_as_nones(db, monkeypatch):
    """When ping_hosts returns an empty RTT list for a host, ping_count Nones are stored."""
    config = _make_config(host="10.0.0.1", name="Unreachable", ping_count=5)

    async def mock_ping(hosts, **kwargs):
        return {"10.0.0.1": []}  # All loss

    monkeypatch.setattr("netsmoke.collector.ping_hosts", mock_ping)

    before = int(time.time())
    await _collect_once(config, db)

    rows = await query_samples(db, "Unreachable", before - 1, int(time.time()) + 1)
    assert len(rows) == 5
    assert all(r[2] is None for r in rows)
