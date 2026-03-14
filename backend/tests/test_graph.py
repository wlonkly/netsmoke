"""Tests for graph.py"""

import time
from datetime import datetime, timezone

import numpy as np
import pytest
import pytest_asyncio
import aiosqlite

from netsmoke.db import open_db, insert_samples
from netsmoke.graph import (
    RANGE_SECONDS,
    _loss_color,
    build_rtt_matrix,
    calculate_smoke_bands,
    render_graph,
    render_graph_for_target,
    render_graph_for_window,
)


# --- Unit tests for pure functions ---

def test_loss_color_no_loss():
    c = _loss_color(0)
    assert c == "#00cc00"


def test_loss_color_full_loss():
    c = _loss_color(100)
    # Should be fully red
    assert c.startswith("#ff")


def test_loss_color_interpolates():
    colors = [_loss_color(p) for p in range(0, 101, 10)]
    # All must be valid hex colors
    for c in colors:
        assert c.startswith("#")
        assert len(c) == 7


def test_calculate_smoke_bands_shape():
    num_timestamps = 10
    num_pings = 20
    data = np.sort(np.random.uniform(10, 100, (num_timestamps, num_pings)), axis=1)
    bands = calculate_smoke_bands(data)

    assert len(bands) == num_pings // 2
    for band in bands:
        assert band["bottom"].shape == (num_timestamps,)
        assert band["height"].shape == (num_timestamps,)
        assert band["color"].startswith("#")


def test_calculate_smoke_bands_non_negative_height():
    data = np.sort(np.abs(np.random.normal(50, 10, (20, 20))), axis=1)
    bands = calculate_smoke_bands(data)
    for band in bands:
        assert np.all(band["height"] >= 0)


def test_build_rtt_matrix_basic():
    now = int(time.time())
    rows = [
        (now, 1, 10.0),
        (now, 2, 12.0),
        (now, 3, None),
        (now + 60, 1, 11.0),
        (now + 60, 2, 13.0),
        (now + 60, 3, 11.5),
    ]
    timestamps, matrix, loss_pcts = build_rtt_matrix(rows, num_pings=3)

    assert len(timestamps) == 2
    assert matrix.shape == (2, 3)
    # First timestamp has one None
    assert loss_pcts[0] > 0
    # Second timestamp has no None
    assert loss_pcts[1] == 0.0


def test_build_rtt_matrix_empty():
    timestamps, matrix, loss_pcts = build_rtt_matrix([], num_pings=20)
    assert len(timestamps) == 0
    assert matrix.shape == (0, 20)


def test_render_graph_returns_png_bytes():
    now = int(time.time())
    rows = []
    for i in range(10):
        ts = now + i * 60
        for j in range(20):
            rows.append((ts, j + 1, 10.0 + j))

    timestamps, matrix, loss_pcts = build_rtt_matrix(rows, num_pings=20)
    result = render_graph(
        timestamps, matrix, loss_pcts,
        title="Test",
        start_ts=now - 3 * 3600,
        end_ts=now + 10 * 60,
    )

    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_render_graph_for_window(seeded_db):
    now = int(time.time())
    result = await render_graph_for_window(
        seeded_db, "CDNs/Cloudflare",
        start_ts=now - 3600,
        end_ts=now,
        num_pings=20,
    )
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


def test_render_graph_empty_data_returns_png():
    """Should render a 'no data' placeholder, not crash."""
    result = render_graph([], np.empty((0, 20)), np.empty(0), title="Empty")
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


# --- Integration test with real DB ---

@pytest_asyncio.fixture
async def seeded_db(tmp_path):
    path = str(tmp_path / "test.db")
    db = await open_db(path)

    now = int(time.time())
    for i in range(30):
        ts = now - (29 - i) * 60
        rtts = [10.0 + j + i * 0.1 for j in range(20)]
        # Add some packet loss
        if i % 5 == 0:
            rtts[0] = None
        await insert_samples(db, "CDNs/Cloudflare", ts, rtts)

    yield db
    await db.close()


@pytest.mark.asyncio
async def test_render_graph_for_target(seeded_db):
    result = await render_graph_for_target(
        seeded_db, "CDNs/Cloudflare", "3h", num_pings=20
    )
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_render_graph_no_data_for_target(seeded_db):
    """Target with no data returns a valid empty PNG."""
    result = await render_graph_for_target(
        seeded_db, "nonexistent/target", "3h", num_pings=20
    )
    assert isinstance(result, bytes)
    assert result[:4] == b"\x89PNG"


def test_range_seconds_values():
    assert RANGE_SECONDS["3h"]  == 3 * 3600
    assert RANGE_SECONDS["2d"]  == 2 * 24 * 3600
    assert RANGE_SECONDS["1mo"] == 30 * 24 * 3600
    assert RANGE_SECONDS["1y"]  == 365 * 24 * 3600
