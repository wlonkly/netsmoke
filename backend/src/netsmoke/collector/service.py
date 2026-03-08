from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from threading import Lock

import numpy as np

from netsmoke.probes.fping import FPingProbe, ProbeExecutionError
from netsmoke.services.targets import store_measurement_batch
from netsmoke.services.tree import get_config, get_flat_targets
from netsmoke.services.types import CollectedRound, CollectorRuntimeState
from netsmoke.settings import settings

logger = logging.getLogger(__name__)

_state_lock = Lock()
_runtime_state = CollectorRuntimeState(enabled=settings.collector_enabled, status='disabled' if not settings.collector_enabled else 'idle')


class CollectorService:
    def __init__(self, probe: FPingProbe | None = None) -> None:
        self.probe = probe or FPingProbe(settings.fping_binary)

    async def collect_once(self) -> list[CollectedRound]:
        config = get_config(settings.config_path)
        targets = list(get_flat_targets(settings.config_path))
        if not targets:
            logger.info('collector round skipped: no configured targets')
            return []

        logger.info(
            'collector round starting',
            extra={'target_count': len(targets), 'pings': config.defaults.pings},
        )
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
            round_ = CollectedRound(
                target_slug=target.id,
                observed_at=observed_at,
                samples=samples,
                sent=sent,
                received=received,
                loss_pct=loss_pct,
                median_rtt_ms=median_rtt_ms,
            )
            rounds.append(round_)
            logger.info(
                'collector target summary',
                extra={
                    'target_slug': target.id,
                    'host': target.host,
                    'sent': sent,
                    'received': received,
                    'loss_pct': round(loss_pct, 3),
                    'median_rtt_ms': median_rtt_ms,
                    'samples': samples,
                },
            )

        return rounds

    async def collect_and_store(self) -> list[CollectedRound]:
        started_at = datetime.now(UTC)
        _update_runtime_state(status='running', last_started_at=started_at, last_error=None)
        try:
            rounds = await self.collect_once()
            await store_measurement_batch(rounds)
            finished_at = datetime.now(UTC)
            _update_runtime_state(
                status='idle',
                last_finished_at=finished_at,
                last_success_at=finished_at,
                last_round_target_count=len(rounds),
                last_round_persisted_count=len(rounds),
                last_round_summary=[
                    {
                        'targetSlug': round_.target_slug,
                        'sent': round_.sent,
                        'received': round_.received,
                        'lossPct': round_.loss_pct,
                        'medianRttMs': round_.median_rtt_ms,
                    }
                    for round_ in rounds[:10]
                ],
            )
            logger.info('collector round persisted', extra={'persisted_count': len(rounds)})
            return rounds
        except ProbeExecutionError as exc:
            finished_at = datetime.now(UTC)
            _update_runtime_state(
                status='error',
                last_finished_at=finished_at,
                last_error=str(exc),
                last_error_at=finished_at,
                last_round_persisted_count=0,
            )
            logger.warning('collector probe failed: %s', exc)
            raise
        except Exception as exc:
            finished_at = datetime.now(UTC)
            _update_runtime_state(
                status='error',
                last_finished_at=finished_at,
                last_error=str(exc),
                last_error_at=finished_at,
                last_round_persisted_count=0,
            )
            logger.exception('collector iteration failed')
            raise

    async def run_forever(self) -> None:
        while True:
            try:
                await self.collect_and_store()
            except ProbeExecutionError:
                pass
            except Exception:
                pass

            step_seconds = get_config(settings.config_path).defaults.step_seconds
            await asyncio.sleep(step_seconds)



def get_collector_runtime_state() -> dict[str, object]:
    with _state_lock:
        return _runtime_state.as_dict()



def initialize_collector_runtime_state(enabled: bool) -> None:
    status = 'idle' if enabled else 'disabled'
    with _state_lock:
        _runtime_state.enabled = enabled
        _runtime_state.status = status



def _update_runtime_state(**updates: object) -> None:
    with _state_lock:
        for key, value in updates.items():
            setattr(_runtime_state, key, value)
