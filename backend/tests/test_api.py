"""Integration tests for api.py using httpx + FastAPI test client."""

import time

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from netsmoke.api import create_app, set_state
from netsmoke.config import load_config
from netsmoke.db import open_db, insert_samples

import textwrap
from pathlib import Path


def _write_config(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent("""
        settings:
          ping_count: 5
          ping_interval: 60
        targets:
          - name: "Google DNS"
            host: "8.8.8.8"
          - folder: "CDNs"
            targets:
              - name: "Cloudflare"
                host: "1.1.1.1"
    """))
    return p


@pytest_asyncio.fixture
async def client(tmp_path):
    cfg_path = _write_config(tmp_path)
    config = load_config(cfg_path)
    db = await open_db(str(tmp_path / "test.db"))

    # Seed some data
    now = int(time.time())
    for i in range(5):
        ts = now - i * 60
        await insert_samples(db, "Google DNS", ts, [10.0, 11.0, 12.0, None, 13.0])
        await insert_samples(db, "CDNs/Cloudflare", ts, [5.0, 6.0, 7.0, 8.0, 9.0])

    app = create_app()
    set_state(config, db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    await db.close()


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_get_targets(client):
    resp = await client.get("/api/targets")
    assert resp.status_code == 200
    tree = resp.json()
    assert isinstance(tree, list)
    assert len(tree) == 2

    # First item is a root target
    assert tree[0]["type"] == "target"
    assert tree[0]["name"] == "Google DNS"
    assert tree[0]["path"] == "Google DNS"

    # Second item is a folder
    assert tree[1]["type"] == "folder"
    assert tree[1]["name"] == "CDNs"
    assert len(tree[1]["children"]) == 1


@pytest.mark.asyncio
async def test_get_graph_png(client):
    resp = await client.get("/api/graph/Google DNS")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_get_graph_nested_target(client):
    resp = await client.get("/api/graph/CDNs/Cloudflare")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_get_graph_with_range(client):
    for r in ("3h", "2d", "1mo", "1y"):
        resp = await client.get(f"/api/graph/Google DNS?range={r}")
        assert resp.status_code == 200, f"Failed for range={r}"


@pytest.mark.asyncio
async def test_get_graph_invalid_range(client):
    resp = await client.get("/api/graph/Google DNS?range=999h")
    assert resp.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_get_graph_not_found(client):
    resp = await client.get("/api/graph/nonexistent/target")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_graph_with_start_end(client):
    now = int(time.time())
    resp = await client.get(
        f"/api/graph/Google DNS?start={now - 3600}&end={now}"
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_get_stats(client):
    resp = await client.get("/api/targets/Google DNS/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"] == "Google DNS"
    assert "median_ms" in data
    assert "loss_pct" in data
    assert "sample_count" in data


@pytest.mark.asyncio
async def test_get_stats_not_found(client):
    resp = await client.get("/api/targets/nonexistent/stats")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_graph_start_without_end_falls_back_to_range(client):
    """Providing start but not end falls back to range-based rendering."""
    now = int(time.time())
    resp = await client.get(f"/api/graph/Google DNS?start={now - 3600}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_get_stats_window_below_minimum(client):
    """window=59 is below the minimum of 60 and should return 422."""
    resp = await client.get("/api/targets/Google DNS/stats?window=59")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_stats_window_above_maximum(client):
    """window=86401 is above the maximum of 86400 and should return 422."""
    resp = await client.get("/api/targets/Google DNS/stats?window=86401")
    assert resp.status_code == 422
