from datetime import UTC

import pytest

from netsmoke.collector.service import CollectorService
from netsmoke.services.tree import get_config, get_flat_targets, get_tree
from netsmoke.settings import settings


class StubProbe:
    async def run(self, hosts, *, count, timeout_seconds, packet_size_bytes):
        del timeout_seconds, packet_size_bytes
        return {
            hosts[0]: [10.0, 12.0, 11.0, None][:count],
        }


@pytest.mark.asyncio
async def test_collect_once_builds_rounds(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / 'netsmoke.yaml'
    config_file.write_text(
        '''
        defaults:
          pings: 4
        targets:
          - name: Core
            type: folder
            children:
              - name: gateway
                type: host
                host: 192.0.2.1
        '''
    )

    monkeypatch.setattr(settings, 'config_path', config_file)
    get_tree.cache_clear()
    get_flat_targets.cache_clear()
    get_config.cache_clear()

    rounds = await CollectorService(probe=StubProbe()).collect_once()

    assert len(rounds) == 1
    round_ = rounds[0]
    assert round_.target_slug == 'core-gateway'
    assert round_.sent == 4
    assert round_.received == 3
    assert round_.loss_pct == 25.0
    assert round_.median_rtt_ms == 11.0
    assert round_.observed_at.tzinfo == UTC
