"""
matplotlib smoke graph generator.

Ports the algorithm from smoke_poc_bars.py and adds DB-backed rendering.
"""

from __future__ import annotations

import asyncio
import io
import time
from collections import OrderedDict
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend, must be set before pyplot import
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from matplotlib.patches import Patch
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

CACHE_TTL = 60       # seconds; matches default collection interval
CACHE_MAXSIZE = 512  # max entries before LRU eviction
MAX_RENDER_POINTS = 200  # sub-sample to at most this many data points per graph


class _TTLCache:
    """In-memory TTL cache with LRU eviction. Thread-safe for asyncio use."""
    def __init__(self, maxsize: int = CACHE_MAXSIZE, ttl: float = CACHE_TTL):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: tuple) -> bytes | None:
        if key not in self._cache:
            return None
        ts, value = self._cache[key]
        if time.monotonic() - ts > self._ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return value

    def set(self, key: tuple, value: bytes) -> None:
        self._cache[key] = (time.monotonic(), value)
        self._cache.move_to_end(key)
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()


_graph_cache = _TTLCache()


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

    Groups by timestamp, then sub-samples to at most MAX_RENDER_POINTS
    evenly-spaced timestamps so the matrix is bounded.

    rows: list of (time, sample_num, rtt_ms)
    Returns:
        timestamps: list of datetime objects (one per measurement)
        rtt_matrix: shape (N, num_pings), NaN for lost packets
        loss_pcts:  shape (N,), fraction 0..1 of lost packets
    """
    by_time: dict[int, list[Optional[float]]] = {}
    for ts, sample_num, rtt in rows:
        by_time.setdefault(ts, []).append(rtt)

    if not by_time:
        return [], np.empty((0, num_pings)), np.empty(0)

    sorted_times = sorted(by_time.keys())
    n = len(sorted_times)
    if n > MAX_RENDER_POINTS:
        indices = np.linspace(0, n - 1, MAX_RENDER_POINTS).astype(int)
        sorted_times = [sorted_times[i] for i in indices]

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

    Sub-samples to at most MAX_RENDER_POINTS evenly-spaced buckets
    so the resulting matrix is bounded regardless of window size.

    rollup_rows: list of dicts with keys bucket_start, sorted_rtts, loss_count, total_count
    Returns same tuple as build_rtt_matrix.
    """
    if not rollup_rows:
        return [], np.empty((0, num_pings)), np.empty(0)

    n = len(rollup_rows)
    if n > MAX_RENDER_POINTS:
        indices = np.linspace(0, n - 1, MAX_RENDER_POINTS).astype(int)
        rollup_rows = [rollup_rows[i] for i in indices]

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

    This function does NOT use pyplot, so it is safe to call from
    asyncio.to_thread() or concurrent.futures threads.

    Returns PNG bytes.
    """
    fig = Figure(figsize=(12, 4))
    ax = fig.add_subplot(111)
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
        _style_axes(fig, ax, title, duration_s)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
        fig.clear()
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
            step="mid",
        )

    _style_axes(fig, ax, title, duration_s)

    # Median lines: a thin horizontal line at the median RTT for each
    # time slot, colored by loss percentage — matches SmokePing's appearance.
    medians = np.median(display_matrix, axis=1)
    valid_mask = ~np.isnan(medians) & (medians > 0)
    valid_meds = medians[valid_mask]
    valid_x = x[valid_mask]
    valid_colors = [_loss_color(l * 100) for l in loss_pcts[valid_mask]]

    ax.hlines(valid_meds, valid_x - width / 2, valid_x + width / 2,
              colors=valid_colors, linewidth=2, zorder=100)

    legend_elements = [
        Patch(color="#00cc00", label="0% loss"),
        Patch(color="#0000ff", label="25%"),
        Patch(color="#800080", label="50%"),
        Patch(color="#ffa500", label="75%"),
        Patch(color="#ff0000", label="100%"),
    ]
    ax.legend(
        handles=legend_elements, title="Loss",
        loc="upper right", bbox_to_anchor=(1.0, -0.15),
        ncol=5, fontsize=7, title_fontsize=8,
        framealpha=0.8, edgecolor="#ccccdd",
    )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.clear()
    return buf.getvalue()


def _style_axes(fig: Figure, ax, title: str, duration_s: float) -> None:
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

    fig.autofmt_xdate(rotation=30, ha="right")
    fig.subplots_adjust(bottom=0.15)


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
    Otherwise queries raw ping_samples. Results are cached in-memory with a
    60-second TTL and 60-second timestamp quantization.
    """
    # Quantize timestamps to 60s boundaries so concurrent/repeated requests
    # within the same window share a cache entry.
    start_ts = (start_ts // 60) * 60
    end_ts = (end_ts // 60) * 60
    cache_key = (target, start_ts, end_ts, num_pings, bucket_size)

    cached = _graph_cache.get(cache_key)
    if cached is not None:
        return cached

    _BUCKET_SECONDS = {"hour": 3600.0, "day": 86400.0}

    if bucket_size is None:
        # Sub-sample at the SQL level: estimate total timestamps from the
        # window size and add a modulo filter so SQLite only returns ~1/step
        # of the rows. The covering index handles this as an index-only scan.
        est_timestamps = max(1, (end_ts - start_ts) // 60)
        step = max(1, est_timestamps // MAX_RENDER_POINTS)
        if step > 1:
            offset = start_ts % step
            async with db.execute(
                "SELECT time, sample_num, rtt_ms FROM ping_samples "
                "WHERE target = ? AND time >= ? AND time <= ? AND (time % ?) = ? "
                "ORDER BY time, sample_num",
                (target, start_ts, end_ts, step, offset),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            from netsmoke.db import query_samples
            rows = await query_samples(db, target, start_ts, end_ts)
        timestamps, rtt_matrix, loss_pcts = build_rtt_matrix(rows, num_pings)
        bar_width_seconds = 60.0  # one measurement interval
    else:
        from netsmoke.db import query_rollups
        rows = await query_rollups(db, target, start_ts, end_ts, bucket_size)
        timestamps, rtt_matrix, loss_pcts = build_rollup_rtt_matrix(rows, num_pings)
        bar_width_seconds = _BUCKET_SECONDS[bucket_size]

    # Offload matplotlib rendering to a thread so it doesn't block the
    # asyncio event loop. Other requests (health, targets, stats) can
    # proceed while the graph renders on a thread-pool worker.
    png_bytes = await asyncio.to_thread(
        render_graph, timestamps, rtt_matrix, loss_pcts,
        title=target, start_ts=start_ts, end_ts=end_ts,
        bar_width_seconds=bar_width_seconds,
    )
    _graph_cache.set(cache_key, png_bytes)
    return png_bytes


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
