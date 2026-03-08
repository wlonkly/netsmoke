from datetime import UTC, datetime, timedelta
from io import StringIO

import matplotlib
matplotlib.use('svg')
import matplotlib.pyplot as plt
import numpy as np
from fastapi import APIRouter, HTTPException, Response
from matplotlib.dates import DateFormatter, date2num

from netsmoke.services.targets import (
    get_latest_measurement_map,
    get_target_by_slug,
    pending_measurement,
    target_record_to_payload,
)
from netsmoke.services.tree import FolderRecord, TargetRecord, get_flat_targets, get_tree
from netsmoke.settings import settings

router = APIRouter()


@router.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok'}


@router.get('/collector/status')
async def collector_status() -> dict[str, str | bool]:
    return {'status': 'idle', 'enabled': settings.collector_enabled}


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
    payload = target_record_to_payload(target_record, latest.get(target_id, pending_measurement()))
    payload['enabled'] = db_target.enabled
    return payload


@router.get('/targets/{target_id}/graph.svg')
async def graph_svg(target_id: str, range: str = '6h') -> Response:
    target = _get_config_target_or_404(target_id)
    del range

    timestamps, samples = _generate_demo_samples(target.id)
    svg = _render_demo_graph(timestamps, samples, title=target.path)
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



def _generate_demo_samples(seed_hint: str, num_timestamps: int = 132, num_pings: int = 20) -> tuple[list[datetime], np.ndarray]:
    seed = sum(ord(character) for character in seed_hint) % 10_000
    rng = np.random.default_rng(seed)
    start_time = datetime.now(UTC) - timedelta(hours=11)
    timestamps = [start_time + timedelta(minutes=5 * index) for index in range(num_timestamps)]
    rows = []
    base_latency = 32.0 + (seed % 30)

    for index in range(num_timestamps):
        trend = 6.0 * np.sin(index / 20) + 2.5 * np.sin(index / 7)
        congestion = rng.uniform(15, 75) if rng.random() < 0.11 else 0.0
        jitter = 4.0 + congestion * 0.18
        mean_latency = base_latency + trend + congestion

        pings = rng.normal(mean_latency, jitter, num_pings)
        pings = np.maximum(pings, 1.0)

        if rng.random() < 0.1:
            loss_count = int(rng.integers(1, max(2, num_pings // 2)))
            lost_indices = rng.choice(num_pings, size=loss_count, replace=False)
            pings[lost_indices] = np.nan

        rows.append(pings)

    return timestamps, np.array(rows)



def _render_demo_graph(timestamps: list[datetime], samples: np.ndarray, title: str) -> str:
    valid = np.where(np.isnan(samples), np.nan, samples)
    median = np.nanmedian(valid, axis=1)
    q1 = np.nanpercentile(valid, 25, axis=1)
    q3 = np.nanpercentile(valid, 75, axis=1)
    loss_ratio = np.mean(np.isnan(samples), axis=1)

    fig, ax = plt.subplots(figsize=(13, 5.8), facecolor='#ffffff')
    ax.set_facecolor('#fcfcfc')

    x_values = date2num(timestamps)
    slot_width = np.min(np.diff(x_values)) if len(x_values) > 1 else 1.0 / 24.0

    for band in _calculate_smoke_bands(samples):
        ax.bar(
            x_values,
            band['height'],
            width=slot_width,
            bottom=band['bottom'],
            color=band['color'],
            linewidth=0,
            edgecolor='none',
            align='center',
            zorder=2,
        )

    marker_height = np.maximum(0.7, (q3 - q1) * 0.12)
    marker_height = np.where(np.isnan(marker_height), 0.9, marker_height)
    marker_bottom = median - (marker_height / 2)
    marker_colors = [_loss_color(value) for value in loss_ratio]

    ax.bar(
        x_values,
        marker_height,
        width=slot_width,
        bottom=marker_bottom,
        color=marker_colors,
        linewidth=0,
        edgecolor='none',
        align='center',
        zorder=5,
    )

    ax.set_title(title, fontsize=14, loc='left')
    ax.set_ylabel('Latency (ms)')
    ax.set_xlabel('Time')
    ax.grid(True, axis='y', alpha=0.18, linestyle='--', zorder=0)
    ax.grid(False, axis='x')
    ax.set_ylim(bottom=0)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(0.9)
    ax.spines['bottom'].set_linewidth(0.9)
    ax.spines['left'].set_color('#666666')
    ax.spines['bottom'].set_color('#666666')
    ax.xaxis.set_major_formatter(DateFormatter('%H:%M'))
    fig.autofmt_xdate()
    plt.tight_layout()

    buffer = StringIO()
    fig.savefig(buffer, format='svg')
    plt.close(fig)
    return buffer.getvalue()



def _calculate_smoke_bands(samples: np.ndarray) -> list[dict[str, np.ndarray | str]]:
    sorted_samples = np.sort(np.where(np.isnan(samples), np.inf, samples), axis=1)
    half = samples.shape[1] // 2
    bands: list[dict[str, np.ndarray | str]] = []

    for lower_index in range(half):
        upper_index = samples.shape[1] - 1 - lower_index
        gray_value = int(190 / half * (half - lower_index)) + 50
        color = f'#{gray_value:02x}{gray_value:02x}{gray_value:02x}'
        bottom = sorted_samples[:, lower_index].copy()
        top = sorted_samples[:, upper_index].copy()
        missing = np.isinf(bottom) | np.isinf(top)
        bottom[missing] = np.nan
        top[missing] = np.nan
        bands.append({'bottom': bottom, 'height': top - bottom, 'color': color})

    return bands



def _loss_color(loss_ratio: float) -> str:
    if loss_ratio == 0:
        return '#00cc00'
    if loss_ratio <= 0.1:
        return '#0066ff'
    if loss_ratio <= 0.25:
        return '#8b3fbf'
    if loss_ratio <= 0.5:
        return '#ff9900'
    return '#cc0000'
