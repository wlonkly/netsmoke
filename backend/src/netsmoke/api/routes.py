from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response

from netsmoke.collector.service import get_collector_runtime_state
from netsmoke.graphs.smoke import render_smoke_svg
from netsmoke.services.targets import (
    get_graph_series,
    get_latest_measurement_map,
    get_recent_measurements,
    get_target_by_slug,
    pending_measurement,
    recent_measurement_to_payload,
    target_record_to_payload,
)
from netsmoke.services.tree import FolderRecord, TargetRecord, get_flat_targets, get_tree
from netsmoke.settings import settings

router = APIRouter()


@router.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok'}


@router.get('/collector/status')
async def collector_status() -> dict[str, object]:
    return get_collector_runtime_state()


@router.get('/tree')
async def tree() -> dict[str, list[dict[str, object]]]:
    config_tree = get_tree(settings.config_path)
    targets = list(get_flat_targets(settings.config_path))
    latest_by_id = await get_latest_measurement_map([target.id for target in targets])
    return {
        'tree': [_serialize_node(node, latest_by_id) for node in config_tree],
        'targets': [
            target_record_to_payload(target, latest_by_id.get(target.id, pending_measurement()))
            for target in targets
        ],
    }


@router.get('/targets/{target_id}')
async def target_detail(target_id: str) -> dict[str, object]:
    target_record = _get_config_target_or_404(target_id)
    db_target = await get_target_by_slug(target_id)
    if db_target is None:
        raise HTTPException(status_code=404, detail='Target not found in database')

    latest = await get_latest_measurement_map([target_id])
    recent_measurements = await get_recent_measurements(target_id, limit=10)
    payload = target_record_to_payload(target_record, latest.get(target_id, pending_measurement()))
    payload['enabled'] = db_target.enabled
    payload['recentMeasurements'] = [recent_measurement_to_payload(item) for item in recent_measurements]
    return payload


@router.get('/targets/{target_id}/graph.svg')
async def graph_svg(target_id: str, range: str = '6h') -> Response:
    target = _get_config_target_or_404(target_id)
    graph_series = await get_graph_series(target.id, _range_to_start(range))
    svg = render_smoke_svg(target.path, list(graph_series.timestamps), graph_series.samples)
    return Response(content=svg, media_type='image/svg+xml')



def _serialize_node(node: FolderRecord | TargetRecord, latest_by_id: dict[str, dict[str, object]]) -> dict[str, object]:
    if isinstance(node, TargetRecord):
        return {
            'id': node.id,
            'name': node.name,
            'type': 'host',
            'path': node.path,
            'host': node.host,
            'lastMeasurement': latest_by_id.get(node.id, pending_measurement()),
        }

    return {
        'id': node.id,
        'name': node.name,
        'type': 'folder',
        'path': node.path,
        'children': [_serialize_node(child, latest_by_id) for child in node.children],
    }



def _get_config_target_or_404(target_id: str) -> TargetRecord:
    for target in get_flat_targets(settings.config_path):
        if target.id == target_id:
            return target
    raise HTTPException(status_code=404, detail='Target not found')



def _range_to_start(raw_range: str) -> datetime:
    amount = int(raw_range[:-1])
    unit = raw_range[-1]
    now = datetime.now(UTC)
    if unit == 'm':
        return now - timedelta(minutes=amount)
    if unit == 'h':
        return now - timedelta(hours=amount)
    if unit == 'd':
        return now - timedelta(days=amount)
    raise HTTPException(status_code=400, detail='Unsupported range')
