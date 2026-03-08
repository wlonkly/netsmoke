from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import StringIO

import matplotlib
matplotlib.use('svg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.dates import DateFormatter, date2num


@dataclass(slots=True)
class SmokeBand:
    bottom: np.ndarray
    height: np.ndarray
    color: str



def calculate_smoke_bands(samples: np.ndarray) -> list[SmokeBand]:
    if samples.size == 0:
        return []

    sorted_samples = np.sort(np.where(np.isnan(samples), np.inf, samples), axis=1)
    half = samples.shape[1] // 2
    bands: list[SmokeBand] = []

    for lower_index in range(half):
        upper_index = samples.shape[1] - 1 - lower_index
        gray_value = int(190 / half * (half - lower_index)) + 50
        color = f'#{gray_value:02x}{gray_value:02x}{gray_value:02x}'
        bottom = sorted_samples[:, lower_index].copy()
        top = sorted_samples[:, upper_index].copy()
        missing = np.isinf(bottom) | np.isinf(top)
        bottom[missing] = np.nan
        top[missing] = np.nan
        bands.append(SmokeBand(bottom=bottom, height=top - bottom, color=color))

    return bands



def render_smoke_svg(title: str, timestamps: list[datetime], samples: np.ndarray) -> str:
    fig, ax = plt.subplots(figsize=(13, 5.8), facecolor='#ffffff')
    ax.set_facecolor('#fcfcfc')

    if samples.size == 0 or not timestamps:
        ax.set_title(title, fontsize=14, loc='left')
        ax.set_ylabel('Latency (ms)')
        ax.set_xlabel('Time')
        ax.text(0.5, 0.5, 'No measurements yet', ha='center', va='center', transform=ax.transAxes)
        ax.grid(True, axis='y', alpha=0.18, linestyle='--', zorder=0)
        ax.grid(False, axis='x')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_linewidth(0.9)
        ax.spines['bottom'].set_linewidth(0.9)
        ax.spines['left'].set_color('#666666')
        ax.spines['bottom'].set_color('#666666')
        plt.tight_layout()
        return _figure_to_svg(fig)

    valid = np.where(np.isnan(samples), np.nan, samples)
    median = np.nanmedian(valid, axis=1)
    q1 = np.nanpercentile(valid, 25, axis=1)
    q3 = np.nanpercentile(valid, 75, axis=1)
    loss_ratio = np.mean(np.isnan(samples), axis=1)

    x_values = date2num(timestamps)
    slot_width = np.min(np.diff(x_values)) if len(x_values) > 1 else 1.0 / 24.0

    for band in calculate_smoke_bands(samples):
        ax.bar(
            x_values,
            band.height,
            width=slot_width,
            bottom=band.bottom,
            color=band.color,
            linewidth=0,
            edgecolor='none',
            align='center',
            zorder=2,
        )

    marker_height = np.maximum(0.7, (q3 - q1) * 0.12)
    marker_height = np.where(np.isnan(marker_height), 0.9, marker_height)
    marker_bottom = median - (marker_height / 2)
    marker_colors = [loss_color(value) for value in loss_ratio]

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
    return _figure_to_svg(fig)



def loss_color(loss_ratio: float) -> str:
    if loss_ratio == 0:
        return '#00cc00'
    if loss_ratio <= 0.1:
        return '#0066ff'
    if loss_ratio <= 0.25:
        return '#8b3fbf'
    if loss_ratio <= 0.5:
        return '#ff9900'
    return '#cc0000'



def _figure_to_svg(fig: plt.Figure) -> str:
    buffer = StringIO()
    fig.savefig(buffer, format='svg')
    plt.close(fig)
    return buffer.getvalue()
