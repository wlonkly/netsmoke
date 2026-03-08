from __future__ import annotations

from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlalchemy import and_, func, select

from netsmoke.db.session import get_session_factory
from netsmoke.models import MeasurementRound, PingSample, Target
from netsmoke.services.tree import TargetRecord, get_flat_targets
from netsmoke.services.types import CollectedRound, GraphSeries, RecentMeasurement
from netsmoke.settings import settings


async def sync_config_targets() -> None:
    configured_targets = get_flat_targets(settings.config_path)
    session_factory = get_session_factory()

    async with session_factory() as session:
        existing_targets = {
            target.slug: target
            for target in (await session.execute(select(Target))).scalars().all()
        }

        active_ids = {target.id for target in configured_targets}
        for configured_target in configured_targets:
            existing = existing_targets.get(configured_target.id)
            if existing is None:
                session.add(
                    Target(
                        slug=configured_target.id,
                        name=configured_target.name,
                        host=configured_target.host,
                        path=configured_target.path,
                        enabled=True,
                    )
                )
                continue

            existing.name = configured_target.name
            existing.host = configured_target.host
            existing.path = configured_target.path
            existing.enabled = True

        for slug, target in existing_targets.items():
            if slug not in active_ids:
                target.enabled = False

        await session.commit()


async def get_target_by_slug(slug: str) -> Target | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(Target).where(Target.slug == slug))
        return result.scalar_one_or_none()


async def get_latest_measurement_map(target_slugs: list[str]) -> dict[str, dict[str, Any]]:
    if not target_slugs:
        return {}

    session_factory = get_session_factory()
    async with session_factory() as session:
        latest = (
            select(
                MeasurementRound.target_id.label('target_id'),
                func.max(MeasurementRound.observed_at).label('observed_at'),
            )
            .join(Target, Target.id == MeasurementRound.target_id)
            .where(Target.slug.in_(target_slugs))
            .group_by(MeasurementRound.target_id)
            .subquery()
        )

        rows = (
            await session.execute(
                select(
                    Target.slug,
                    MeasurementRound.observed_at,
                    MeasurementRound.median_rtt_ms,
                    MeasurementRound.loss_pct,
                )
                .join(MeasurementRound, MeasurementRound.target_id == Target.id)
                .join(
                    latest,
                    and_(
                        latest.c.target_id == MeasurementRound.target_id,
                        latest.c.observed_at == MeasurementRound.observed_at,
                    ),
                )
            )
        ).all()

    return {
        row.slug: {
            'observedAt': _to_iso(row.observed_at),
            'medianRttMs': row.median_rtt_ms,
            'lossPct': row.loss_pct,
        }
        for row in rows
    }


async def get_recent_measurements(target_slug: str, limit: int = 10) -> list[RecentMeasurement]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(
                    MeasurementRound.observed_at,
                    MeasurementRound.sent,
                    MeasurementRound.received,
                    MeasurementRound.loss_pct,
                    MeasurementRound.median_rtt_ms,
                )
                .join(Target, Target.id == MeasurementRound.target_id)
                .where(Target.slug == target_slug)
                .order_by(MeasurementRound.observed_at.desc())
                .limit(limit)
            )
        ).all()

    return [
        RecentMeasurement(
            observed_at=_ensure_utc(row.observed_at),
            sent=row.sent,
            received=row.received,
            loss_pct=row.loss_pct,
            median_rtt_ms=row.median_rtt_ms,
        )
        for row in rows
    ]


async def store_measurement_batch(rounds: list[CollectedRound]) -> None:
    if not rounds:
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        target_map = {
            target.slug: target
            for target in (
                await session.execute(select(Target).where(Target.slug.in_([round_.target_slug for round_ in rounds])))
            ).scalars().all()
        }

        for round_ in rounds:
            target = target_map.get(round_.target_slug)
            if target is None:
                continue

            measurement_round = MeasurementRound(
                target_id=target.id,
                observed_at=round_.observed_at,
                sent=round_.sent,
                received=round_.received,
                loss_pct=round_.loss_pct,
                median_rtt_ms=round_.median_rtt_ms,
            )
            session.add(measurement_round)
            await session.flush()

            session.add_all(
                [
                    PingSample(
                        measurement_round_id=measurement_round.id,
                        sample_index=index,
                        rtt_ms=rtt_ms,
                    )
                    for index, rtt_ms in enumerate(round_.samples)
                ]
            )

        await session.commit()


async def create_measurement_round(
    *,
    target_slug: str,
    observed_at: datetime,
    sent: int,
    received: int,
    loss_pct: float,
    median_rtt_ms: float | None,
    samples: tuple[float | None, ...] | None = None,
) -> None:
    samples = samples or tuple(None for _ in range(sent))
    await store_measurement_batch(
        [
            CollectedRound(
                target_slug=target_slug,
                observed_at=observed_at,
                samples=samples,
                sent=sent,
                received=received,
                loss_pct=loss_pct,
                median_rtt_ms=median_rtt_ms,
            )
        ]
    )


async def get_graph_series(target_slug: str, start_at: datetime) -> GraphSeries:
    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(MeasurementRound.observed_at, PingSample.sample_index, PingSample.rtt_ms)
                .join(Target, Target.id == MeasurementRound.target_id)
                .join(PingSample, PingSample.measurement_round_id == MeasurementRound.id)
                .where(Target.slug == target_slug, MeasurementRound.observed_at >= start_at)
                .order_by(MeasurementRound.observed_at, PingSample.sample_index)
            )
        ).all()

    if not rows:
        return GraphSeries(timestamps=tuple(), samples=np.empty((0, 0)))

    grouped: 'OrderedDict[datetime, dict[int, float | None]]' = OrderedDict()
    max_index = 0
    for observed_at, sample_index, rtt_ms in rows:
        normalized_observed_at = _ensure_utc(observed_at)
        grouped.setdefault(normalized_observed_at, {})[sample_index] = rtt_ms
        max_index = max(max_index, sample_index)

    timestamps = tuple(grouped.keys())
    matrix = np.full((len(timestamps), max_index + 1), np.nan)
    for row_index, observed_at in enumerate(timestamps):
        for sample_index, rtt_ms in grouped[observed_at].items():
            if rtt_ms is not None:
                matrix[row_index, sample_index] = rtt_ms

    return GraphSeries(timestamps=timestamps, samples=matrix)



def pending_measurement() -> dict[str, Any]:
    return {
        'observedAt': datetime.now(UTC).isoformat(),
        'medianRttMs': None,
        'lossPct': 100.0,
    }



def target_record_to_payload(target: TargetRecord, measurement: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': target.id,
        'name': target.name,
        'path': target.path,
        'host': target.host,
        'lastMeasurement': measurement,
    }



def recent_measurement_to_payload(measurement: RecentMeasurement) -> dict[str, object]:
    return {
        'observedAt': _to_iso(measurement.observed_at),
        'sent': measurement.sent,
        'received': measurement.received,
        'lossPct': measurement.loss_pct,
        'medianRttMs': measurement.median_rtt_ms,
    }



def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)



def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
