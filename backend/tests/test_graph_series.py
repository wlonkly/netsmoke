from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from netsmoke.db.init import initialize_database
from netsmoke.db.session import get_engine, get_session_factory
from netsmoke.services.targets import create_measurement_round, get_graph_series, sync_config_targets
from netsmoke.services.tree import get_flat_targets, get_tree
from netsmoke.settings import settings


@pytest.mark.asyncio
async def test_get_graph_series_returns_raw_sample_matrix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    observed_at = datetime(2026, 3, 8, 3, 0, tzinfo=UTC)
    await create_measurement_round(
        target_slug='examples-example-target',
        observed_at=observed_at,
        sent=4,
        received=3,
        loss_pct=25.0,
        median_rtt_ms=12.0,
        samples=(10.0, 12.0, None, 15.0),
    )

    series = await get_graph_series('examples-example-target', observed_at - timedelta(minutes=5))

    assert series.timestamps == (observed_at,)
    assert series.samples.shape == (1, 4)
    assert series.samples[0, 0] == 10.0
    assert series.samples[0, 1] == 12.0
    assert series.samples[0, 3] == 15.0
    assert str(series.samples[0, 2]) == 'nan'
