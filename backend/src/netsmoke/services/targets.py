from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select

from netsmoke.db.session import get_session_factory
from netsmoke.models import MeasurementRound, Target
from netsmoke.services.tree import TargetRecord, get_flat_targets
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


async def create_measurement_round(
    *,
    target_slug: str,
    observed_at: datetime,
    sent: int,
    received: int,
    loss_pct: float,
    median_rtt_ms: float | None,
) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        target = (
            await session.execute(select(Target).where(Target.slug == target_slug))
        ).scalar_one()
        session.add(
            MeasurementRound(
                target_id=target.id,
                observed_at=observed_at,
                sent=sent,
                received=received,
                loss_pct=loss_pct,
                median_rtt_ms=median_rtt_ms,
            )
        )
        await session.commit()



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



def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
