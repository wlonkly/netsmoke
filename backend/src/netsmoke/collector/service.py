from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import numpy as np

from netsmoke.probes.fping import FPingProbe, ProbeExecutionError
from netsmoke.services.targets import store_measurement_batch
from netsmoke.services.tree import get_config, get_flat_targets
from netsmoke.services.types import CollectedRound
from netsmoke.settings import settings

logger = logging.getLogger(__name__)


class CollectorService:
    def __init__(self, probe: FPingProbe | None = None) -> None:
        self.probe = probe or FPingProbe(settings.fping_binary)

    async def collect_once(self) -> list[CollectedRound]:
        config = get_config(settings.config_path)
        targets = list(get_flat_targets(settings.config_path))
        if not targets:
            return []

        host_results = await self.probe.run(
            [target.host for target in targets],
            count=config.defaults.pings,
            timeout_seconds=config.defaults.timeout_seconds,
            packet_size_bytes=config.defaults.packet_size_bytes,
        )

        observed_at = datetime.now(UTC)
        rounds: list[CollectedRound] = []
        for target in targets:
            samples = tuple(host_results.get(target.host, [None] * config.defaults.pings))
            successful = [sample for sample in samples if sample is not None]
            sent = len(samples)
            received = len(successful)
            loss_pct = ((sent - received) / sent * 100.0) if sent else 100.0
            median_rtt_ms = float(np.median(successful)) if successful else None
            rounds.append(
                CollectedRound(
                    target_slug=target.id,
                    observed_at=observed_at,
                    samples=samples,
                    sent=sent,
                    received=received,
                    loss_pct=loss_pct,
                    median_rtt_ms=median_rtt_ms,
                )
            )

        return rounds

    async def collect_and_store(self) -> list[CollectedRound]:
        rounds = await self.collect_once()
        await store_measurement_batch(rounds)
        return rounds

    async def run_forever(self) -> None:
        while True:
            try:
                await self.collect_and_store()
            except ProbeExecutionError as exc:
                logger.warning('collector probe failed: %s', exc)
            except Exception:
                logger.exception('collector iteration failed')

            step_seconds = get_config(settings.config_path).defaults.step_seconds
            await asyncio.sleep(step_seconds)
