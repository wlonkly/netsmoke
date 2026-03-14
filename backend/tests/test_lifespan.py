"""Tests for the FastAPI app lifespan (startup/shutdown)."""

import asyncio
import textwrap

import pytest

import netsmoke.api as api_module
from netsmoke.api import _lifespan, create_app, get_config, get_db
from netsmoke.config import load_config
from netsmoke.db import open_db


def _write_config(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent("""
        settings:
          ping_count: 5
          ping_interval: 60
        targets:
          - name: "Loopback"
            host: "127.0.0.1"
    """))
    return p


@pytest.mark.asyncio
async def test_lifespan_initializes_state(tmp_path, monkeypatch):
    """When no state is pre-injected, lifespan loads config and DB from env vars."""
    monkeypatch.setattr(api_module, "_config", None)
    monkeypatch.setattr(api_module, "_db", None)

    cfg_path = _write_config(tmp_path)
    monkeypatch.setenv("NETSMOKE_CONFIG", str(cfg_path))
    monkeypatch.setenv("NETSMOKE_DB", str(tmp_path / "test.db"))

    async def _noop_collector(config, db):
        await asyncio.sleep(3600)

    monkeypatch.setattr("netsmoke.collector.run_collector", _noop_collector)

    app = create_app()
    async with _lifespan(app):
        config = get_config()
        db = get_db()
        assert config is not None
        assert len(config.all_targets) == 1
        assert config.all_targets[0].host == "127.0.0.1"
        assert db is not None


@pytest.mark.asyncio
async def test_lifespan_skips_when_state_preinjected(tmp_path, monkeypatch):
    """Lifespan is a pass-through when set_state() was already called."""
    cfg_path = _write_config(tmp_path)
    config = load_config(cfg_path)
    db = await open_db(str(tmp_path / "test.db"))

    monkeypatch.setattr(api_module, "_config", config)
    monkeypatch.setattr(api_module, "_db", db)

    collector_started = False

    async def _track_start(config, db):
        nonlocal collector_started
        collector_started = True
        await asyncio.sleep(3600)

    monkeypatch.setattr("netsmoke.collector.run_collector", _track_start)

    app = create_app()
    async with _lifespan(app):
        pass

    assert not collector_started
    await db.close()


@pytest.mark.asyncio
async def test_lifespan_collector_cancelled_on_shutdown(tmp_path, monkeypatch):
    """Collector task is cancelled when the lifespan context exits."""
    monkeypatch.setattr(api_module, "_config", None)
    monkeypatch.setattr(api_module, "_db", None)

    cfg_path = _write_config(tmp_path)
    monkeypatch.setenv("NETSMOKE_CONFIG", str(cfg_path))
    monkeypatch.setenv("NETSMOKE_DB", str(tmp_path / "test.db"))

    collector_cancelled = False

    async def _collector(config, db):
        nonlocal collector_cancelled
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            collector_cancelled = True
            raise

    monkeypatch.setattr("netsmoke.collector.run_collector", _collector)

    app = create_app()
    async with _lifespan(app):
        await asyncio.sleep(0)  # yield so the collector task starts running

    assert collector_cancelled
