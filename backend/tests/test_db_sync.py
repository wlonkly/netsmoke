from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from netsmoke.db.init import initialize_database
from netsmoke.db.session import get_engine, get_session_factory
from netsmoke.models import PingSample, Target
from netsmoke.services.targets import create_measurement_round, get_latest_measurement_map, sync_config_targets
from netsmoke.services.tree import get_flat_targets, get_tree
from netsmoke.settings import settings


@pytest.mark.asyncio
async def test_sync_config_targets_creates_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = tmp_path / 'netsmoke.yaml'
    database_file = tmp_path / 'netsmoke.db'
    config_file.write_text(
        '''
        targets:
          - name: Managed
            type: folder
            children:
              - name: Internal
                type: host
                host: 192.0.2.10
        '''
    )

    monkeypatch.setattr(settings, 'config_path', config_file)
    monkeypatch.setattr(settings, 'database_url', f'sqlite+aiosqlite:///{database_file}')
    get_tree.cache_clear()
    get_flat_targets.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    await initialize_database()
    await sync_config_targets()

    async with get_session_factory()() as session:
        rows = (await session.execute(select(Target))).scalars().all()

    assert len(rows) == 1
    assert rows[0].slug == 'managed-internal'
    assert rows[0].host == '192.0.2.10'


@pytest.mark.asyncio
async def test_latest_measurement_map_uses_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = tmp_path / 'netsmoke.yaml'
    database_file = tmp_path / 'netsmoke.db'
    config_file.write_text(
        '''
        targets:
          - name: Examples
            type: folder
            children:
              - name: Example Target
                type: host
                host: example.com
        '''
    )

    monkeypatch.setattr(settings, 'config_path', config_file)
    monkeypatch.setattr(settings, 'database_url', f'sqlite+aiosqlite:///{database_file}')
    get_tree.cache_clear()
    get_flat_targets.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    await initialize_database()
    await sync_config_targets()
    await create_measurement_round(
        target_slug='examples-example-target',
        observed_at=datetime(2026, 3, 8, 2, 30, tzinfo=UTC),
        sent=20,
        received=19,
        loss_pct=5.0,
        median_rtt_ms=18.5,
        samples=tuple([18.5] * 19 + [None]),
    )

    latest = await get_latest_measurement_map(['examples-example-target'])

    assert latest['examples-example-target']['medianRttMs'] == 18.5
    assert latest['examples-example-target']['lossPct'] == 5.0


@pytest.mark.asyncio
async def test_create_measurement_round_stores_ping_samples(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = tmp_path / 'netsmoke.yaml'
    database_file = tmp_path / 'netsmoke.db'
    config_file.write_text(
        '''
        targets:
          - name: Examples
            type: folder
            children:
              - name: Example Target
                type: host
                host: example.com
        '''
    )

    monkeypatch.setattr(settings, 'config_path', config_file)
    monkeypatch.setattr(settings, 'database_url', f'sqlite+aiosqlite:///{database_file}')
    get_tree.cache_clear()
    get_flat_targets.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    await initialize_database()
    await sync_config_targets()
    await create_measurement_round(
        target_slug='examples-example-target',
        observed_at=datetime(2026, 3, 8, 4, 0, tzinfo=UTC),
        sent=4,
        received=3,
        loss_pct=25.0,
        median_rtt_ms=12.0,
        samples=(10.0, 12.0, None, 15.0),
    )

    async with get_session_factory()() as session:
        rows = (await session.execute(select(PingSample).order_by(PingSample.sample_index))).scalars().all()

    assert [row.rtt_ms for row in rows] == [10.0, 12.0, None, 15.0]
