"""
matplotlib smoke graph generator.

Ports the algorithm from smoke_poc_bars.py and adds DB-backed rendering.
"""

from __future__ import annotations

import io
import time
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend, must be set before pyplot import
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timezone


RANGE_SECONDS = {
    "3h":  3 * 3600,
    "2d":  2 * 24 * 3600,
    "1mo": 30 * 24 * 3600,
    "1y":  365 * 24 * 3600,
}

RANGE_BUCKET_SIZE = {
    "3h":  None,
    "2d":  None,
    "1mo": "hour",
    "1y":  "day",
}


def _loss_color(loss_pct: float) -> str:
    """
    Return a hex color for the median dot based on packet loss percentage.
    green (0%) → blue → purple → orange → red (100%)
    """
    if loss_pct <= 0:
        return "#00cc00"
    elif loss_pct < 25:
        # green → blue
        t = loss_pct / 25
        r = int(0 * (1 - t) + 0 * t)
        g = int(204 * (1 - t) + 0 * t)
        b = int(0 * (1 - t) + 255 * t)
        return f"#{r:02x}{g:02x}{b:02x}"
    elif loss_pct < 50:
        # blue → purple
        t = (loss_pct - 25) / 25
        r = int(0 * (1 - t) + 128 * t)
        g = 0
        b = int(255 * (1 - t) + 0 * t)
        return f"#{r:02x}{g:02x}{b:02x}"
    elif loss_pct < 75:
        # purple → orange
        t = (loss_pct - 50) / 25
        r = int(128 * (1 - t) + 255 * t)
        g = int(0 * (1 - t) + 165 * t)
        b = 0
        return f"#{r:02x}{g:02x}{b:02x}"
    else:
        # orange → red
        t = (loss_pct - 75) / 25
        r = 255
        g = int(165 * (1 - t) + 0 * t)
        b = 0
        return f"#{r:02x}{g:02x}{b:02x}"


def calculate_smoke_bands(sorted_pings: np.ndarray) -> list[dict]:
    """
    Calculate smoke bands from a 2D array of sorted RTT values.

    sorted_pings: shape (num_timestamps, num_pings), already sorted along axis=1.
    Returns list of dicts with 'bottom', 'height', 'color'.
    """
    num_timestamps, num_pings = sorted_pings.shape
    bands = []
    half = num_pings // 2

    for ibot in range(half):
        itop = num_pings - 1 - ibot
        gray_value = int(190 / half * (half - ibot)) + 50
        color = f"#{gray_value:02x}{gray_value:02x}{gray_value:02x}"

        bottom = sorted_pings[:, ibot]
        height = sorted_pings[:, itop] - sorted_pings[:, ibot]

        bands.append({"bottom": bottom, "height": height, "color": color})

    return bands


def build_rtt_matrix(
    rows: list[tuple[int, int, Optional[float]]],
    num_pings: int,
) -> tuple[list[datetime], np.ndarray, np.ndarray]:
    """
    Convert flat DB rows → (timestamps, rtt_matrix, loss_pcts).

    rows: list of (time, sample_num, rtt_ms)
    Returns:
        timestamps: list of datetime objects (one per measurement)
        rtt_matrix: shape (N, num_pings), NaN for lost packets
        loss_pcts:  shape (N,), fraction 0..1 of lost packets
    """
    # Group by timestamp
    by_time: dict[int, list[Optional[float]]] = {}
    for ts, sample_num, rtt in rows:
        by_time.setdefault(ts, []).append(rtt)

    if not by_time:
        return [], np.empty((0, num_pings)), np.empty(0)

    sorted_times = sorted(by_time.keys())
    timestamps = [datetime.fromtimestamp(t, tz=timezone.utc) for t in sorted_times]

    n = len(sorted_times)
    rtt_matrix = np.full((n, num_pings), np.nan)
    loss_pcts = np.zeros(n)

    for i, t in enumerate(sorted_times):
        rtts = by_time[t]
        received = [r for r in rtts if r is not None]
        total = max(len(rtts), num_pings)
        loss_pcts[i] = (total - len(received)) / total if total > 0 else 0.0

        for j, rtt in enumerate(received[:num_pings]):
            rtt_matrix[i, j] = rtt

    return timestamps, rtt_matrix, loss_pcts


def build_rollup_rtt_matrix(
    rollup_rows: list[dict],
    num_pings: int,
) -> tuple[list[datetime], np.ndarray, np.ndarray]:
    """
    Convert rollup dicts → (timestamps, rtt_matrix, loss_pcts).

    rollup_rows: list of dicts with keys bucket_start, sorted_rtts, loss_count, total_count
    Returns same tuple as build_rtt_matrix.
    """
    if not rollup_rows:
        return [], np.empty((0, num_pings)), np.empty(0)

    n = len(rollup_rows)
    timestamps = [datetime.fromtimestamp(r["bucket_start"], tz=timezone.utc) for r in rollup_rows]
    rtt_matrix = np.full((n, num_pings), np.nan)
    loss_pcts = np.zeros(n)

    for i, row in enumerate(rollup_rows):
        rtts = row["sorted_rtts"]
        for j, rtt in enumerate(rtts[:num_pings]):
            rtt_matrix[i, j] = rtt
        total = row["total_count"]
        loss_pcts[i] = row["loss_count"] / total if total > 0 else 0.0

    return timestamps, rtt_matrix, loss_pcts


def _locator_and_format(duration_s: float):
    """Return (locator, formatter) appropriate for the given duration in seconds."""
    if duration_s < 21_600:  # < 6 h
        return mdates.MinuteLocator(byminute=[0, 30]), mdates.DateFormatter("%H:%M")
    elif duration_s < 259_200:  # < 3 d
        return mdates.HourLocator(byhour=range(0, 24, 6)), mdates.DateFormatter("%a %H:%M")
    elif duration_s < 5_184_000:  # < 60 d
        return mdates.DayLocator(interval=3), mdates.DateFormatter("%b %d")
    else:
        return mdates.MonthLocator(), mdates.DateFormatter("%b %Y")


def render_graph(
    timestamps: list[datetime],
    rtt_matrix: np.ndarray,
    loss_pcts: np.ndarray,
    title: str = "Ping Latency",
    start_ts: int = 0,
    end_ts: int = 0,
    bar_width_seconds: Optional[float] = None,
) -> bytes:
    """
    Render a smoke graph from pre-built matrices.

    start_ts / end_ts: Unix timestamps defining the full window to display.
    The x-axis is always pinned to this range so the graph shows the full
    requested period even when data only covers part of it.
    When both are 0, defaults to now-3h to now.

    Returns PNG bytes.
    """
    fig, ax = plt.subplots(figsize=(12, 4))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    now = int(time.time())
    _end_ts = end_ts if end_ts != 0 else now
    _start_ts = start_ts if start_ts != 0 else _end_ts - RANGE_SECONDS["3h"]
    duration_s = _end_ts - _start_ts

    x_end = datetime.fromtimestamp(_end_ts, tz=timezone.utc)
    x_start = datetime.fromtimestamp(_start_ts, tz=timezone.utc)
    ax.set_xlim(mdates.date2num(x_start), mdates.date2num(x_end))

    if len(timestamps) == 0 or rtt_matrix.shape[0] == 0:
        ax.text(
            0.5, 0.5, "No data available",
            transform=ax.transAxes,
            ha="center", va="center",
            color="#888888", fontsize=14,
        )
        _style_axes(ax, title, duration_s)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return buf.getvalue()

    n, num_pings = rtt_matrix.shape

    display_matrix = np.copy(rtt_matrix)
    for i in range(n):
        received = rtt_matrix[i, ~np.isnan(rtt_matrix[i, :])]
        if len(received) == 0:
            display_matrix[i, :] = 0
        else:
            padded = np.concatenate([received, np.full(num_pings - len(received), received[-1])])
            display_matrix[i, :] = padded[:num_pings]

    sorted_pings = np.sort(display_matrix, axis=1)
    bands = calculate_smoke_bands(sorted_pings)

    x = mdates.date2num(timestamps)
    if len(x) > 1:
        # Use median gap so a single outlier close/duplicate timestamp doesn't
        # shrink all bars to near-zero width.
        width = float(np.median(np.diff(x)))
    elif bar_width_seconds is not None:
        width = bar_width_seconds / 86400
    else:
        width = duration_s / 86400 / 100

    for band in bands:
        ax.fill_between(
            x,
            band["bottom"],
            band["bottom"] + band["height"],
            color=band["color"],
            linewidth=0,
            edgecolor="none",
        )

    # Median bar: a thin colored horizontal bar at the median RTT for each
    # time slot, spanning the full column width — matches SmokePing's appearance.
    medians = np.median(display_matrix, axis=1)
    y_max = float(np.nanmax(sorted_pings)) if sorted_pings.size > 0 else 1.0
    bar_h = y_max * 0.04  # 4% of y range

    for xi, med, loss in zip(x, medians, loss_pcts):
        if not np.isnan(med) and med > 0:
            ax.bar(
                [xi], [bar_h], width=width,
                bottom=med - bar_h / 2,
                color=_loss_color(loss * 100),
                linewidth=0, align="center", edgecolor="none",
                zorder=100,
            )

    _style_axes(ax, title, duration_s)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def _style_axes(ax: plt.Axes, title: str, duration_s: float) -> None:
    ax.set_title(title, color="#1a1a2e", fontsize=12, pad=8)
    ax.set_xlabel("Time", color="#555577", fontsize=10)
    ax.set_ylabel("Latency (ms)", color="#555577", fontsize=10)
    ax.tick_params(colors="#555577")
    ax.spines["bottom"].set_color("#ccccdd")
    ax.spines["top"].set_color("#ccccdd")
    ax.spines["left"].set_color("#ccccdd")
    ax.spines["right"].set_color("#ccccdd")
    ax.grid(True, alpha=0.5, linestyle="--", color="#ccccdd", zorder=0)
    ax.set_ylim(bottom=0)

    locator, formatter = _locator_and_format(duration_s)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    plt.gcf().autofmt_xdate(rotation=30, ha="right")


async def render_graph_for_window(
    db,
    target: str,
    start_ts: int,
    end_ts: int,
    num_pings: int = 20,
    bucket_size: Optional[str] = None,
) -> bytes:
    """
    Query the DB and render a graph for the given target and exact time window.

    If bucket_size is provided ("hour" or "day"), queries the rollup table.
    Otherwise queries raw ping_samples.
    """
    _BUCKET_SECONDS = {"hour": 3600.0, "day": 86400.0}

    if bucket_size is None:
        from netsmoke.db import query_samples
        rows = await query_samples(db, target, start_ts, end_ts)
        timestamps, rtt_matrix, loss_pcts = build_rtt_matrix(rows, num_pings)
        bar_width_seconds = 60.0  # one measurement interval
    else:
        from netsmoke.db import query_rollups
        rows = await query_rollups(db, target, start_ts, end_ts, bucket_size)
        timestamps, rtt_matrix, loss_pcts = build_rollup_rtt_matrix(rows, num_pings)
        bar_width_seconds = _BUCKET_SECONDS[bucket_size]

    return render_graph(
        timestamps, rtt_matrix, loss_pcts,
        title=target,
        start_ts=start_ts,
        end_ts=end_ts,
        bar_width_seconds=bar_width_seconds,
    )


async def render_graph_for_target(
    db,
    target: str,
    time_range: str,
    num_pings: int = 20,
) -> bytes:
    """
    Query the DB and render a graph for the given target and named time range.
    """
    seconds = RANGE_SECONDS.get(time_range, RANGE_SECONDS["3h"])
    bucket_size = RANGE_BUCKET_SIZE.get(time_range)
    end_ts = int(time.time())
    start_ts = end_ts - seconds
    return await render_graph_for_window(db, target, start_ts, end_ts, num_pings, bucket_size=bucket_size)
