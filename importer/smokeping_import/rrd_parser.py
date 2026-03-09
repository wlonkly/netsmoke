"""
Parse rrdtool XML dump output into (timestamp, [rtt_ms | None]) rows.

Usage:
    lines = subprocess.check_output(["rrdtool", "dump", path]).decode().splitlines()
    meta = parse_rrd_header(lines)
    for ts, ping_values in iter_rows_finest_first(lines, meta):
        ...  # ping_values are in SECONDS; multiply by 1000 for ms

RRD DS layout for SmokePing FPing:
  index 0  = uptime
  index 1  = loss
  index 2  = median
  index 3  = ping1
  ...
  index N+2 = pingN   (N = ping_count)

Only AVERAGE CFs are used.  Archives with MIN/MAX are skipped.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Iterator


# XML comment line: <!-- / 1234567890 --> (timestamp embedded in comment)
TS_RE = re.compile(r'/\s*(\d+)\s*-->')
# One <v> element per DS per row
VALUE_RE = re.compile(r'<v>([^<]+)</v>')
# RRA attributes
CF_RE = re.compile(r'<cf>\s*(\w+)\s*</cf>')
PDP_RE = re.compile(r'<pdp_per_row>\s*(\d+)\s*</pdp_per_row>')
STEP_RE = re.compile(r'<step>\s*(\d+)\s*</step>')
DS_NAME_RE = re.compile(r'<name>\s*(\w+)\s*</name>')
RRA_START_RE = re.compile(r'<rra>')
RRA_END_RE = re.compile(r'</rra>')
DATABASE_START_RE = re.compile(r'<database>')
DATABASE_END_RE = re.compile(r'</database>')
ROW_START_RE = re.compile(r'<row>')


@dataclass
class RRAMeta:
    index: int
    cf: str
    pdp_per_row: int
    step_seconds: int  # = base_step * pdp_per_row
    row_count: int = 0


@dataclass
class RRDMeta:
    base_step: int
    ds_names: list[str]  # ordered list of DS names
    rras: list[RRAMeta]
    ping_count: int = 0  # number of ping DS indices (DS names starting with "ping")

    def average_rras(self) -> list[RRAMeta]:
        return [r for r in self.rras if r.cf == "AVERAGE"]


def parse_rrd_header(lines: list[str]) -> RRDMeta:
    """
    Read an rrdtool dump, extracting base_step, DS names, and per-RRA metadata.

    In rrdtool dump format, each <rra> block nests its own <database> block.
    We skip over database content so we can collect metadata from all RRAs in
    one pass without loading every row.
    """
    base_step = 300
    ds_names: list[str] = []
    rras: list[RRAMeta] = []

    in_rra = False
    in_database = False
    current_cf: str | None = None
    current_pdp: int | None = None
    rra_index = 0
    got_step = False

    for line in lines:
        stripped = line.strip()

        # Skip over <database>...</database> blocks entirely — they may be huge
        if DATABASE_START_RE.search(stripped):
            in_database = True
            continue
        if DATABASE_END_RE.search(stripped):
            in_database = False
            continue
        if in_database:
            continue

        # Base step appears once near the top of the file
        if not got_step:
            m = STEP_RE.search(stripped)
            if m:
                candidate = int(m.group(1))
                if candidate > 0:
                    base_step = candidate
                    got_step = True

        # DS <name> elements appear in the top-level <ds> blocks (before RRAs)
        if not in_rra:
            m = DS_NAME_RE.search(stripped)
            if m:
                ds_names.append(m.group(1))

        # RRA block open
        if RRA_START_RE.search(stripped):
            in_rra = True
            current_cf = None
            current_pdp = None
            continue

        if in_rra:
            m = CF_RE.search(stripped)
            if m:
                current_cf = m.group(1)

            m = PDP_RE.search(stripped)
            if m:
                current_pdp = int(m.group(1))

            if RRA_END_RE.search(stripped):
                if current_cf and current_pdp is not None:
                    rras.append(RRAMeta(
                        index=rra_index,
                        cf=current_cf,
                        pdp_per_row=current_pdp,
                        step_seconds=base_step * current_pdp,
                    ))
                rra_index += 1
                in_rra = False

    ping_count = sum(1 for n in ds_names if n.startswith("ping"))
    return RRDMeta(
        base_step=base_step,
        ds_names=ds_names,
        rras=rras,
        ping_count=ping_count,
    )


def _ping_ds_indices(meta: RRDMeta) -> list[int]:
    """Return the DS column indices for ping1..pingN."""
    return [i for i, n in enumerate(meta.ds_names) if n.startswith("ping")]


def iter_rra_rows(
    lines: list[str],
    rra_index: int,
    meta: RRDMeta,
) -> Iterator[tuple[int, list[float | None]]]:
    """
    Yield (timestamp, ping_values_in_seconds) for every filled row in the
    given RRA block.

    ping_values_in_seconds[i] is the RTT for ping DS i (in seconds), or None
    if the RRD value is NaN (packet loss / unfilled slot).

    Skips rows where all ping values are None.
    """
    ping_indices = _ping_ds_indices(meta)
    if not ping_indices:
        return

    # Scan to the rra_index-th <rra> block then to its <database>
    current_rra = -1
    in_target_db = False

    for line in lines:
        stripped = line.strip()

        if RRA_START_RE.search(stripped):
            current_rra += 1
            continue

        if current_rra == rra_index and DATABASE_START_RE.search(stripped):
            in_target_db = True
            continue

        if in_target_db and DATABASE_END_RE.search(stripped):
            break

        if not in_target_db:
            continue

        # Parse a row: <!-- / TS --> <row><v>...</v>...</row>
        if not ROW_START_RE.search(stripped):
            continue

        m_ts = TS_RE.search(stripped)
        if not m_ts:
            continue
        ts = int(m_ts.group(1))

        values_raw = VALUE_RE.findall(stripped)
        if not values_raw:
            continue

        ping_values: list[float | None] = []
        for idx in ping_indices:
            if idx >= len(values_raw):
                ping_values.append(None)
                continue
            raw = values_raw[idx].strip()
            if raw.lower() in ("nan", "-nan", "nan ", ""):
                ping_values.append(None)
            else:
                try:
                    ping_values.append(float(raw))
                except ValueError:
                    ping_values.append(None)

        # Skip rows where every ping DS is None (unfilled RRD slots)
        if all(v is None for v in ping_values):
            continue

        yield ts, ping_values


def iter_rows_finest_first(
    lines: list[str],
    meta: RRDMeta,
) -> Iterator[tuple[int, list[float | None]]]:
    """
    Yield (timestamp, ping_values_in_seconds) across all AVERAGE RRAs,
    finest granularity first.  Each timestamp is yielded at most once.

    This merges the multi-resolution archives so that coarser archives
    only contribute timestamps not already covered by finer ones.
    """
    average_rras = sorted(meta.average_rras(), key=lambda r: r.step_seconds)
    seen: set[int] = set()

    for rra in average_rras:
        for ts, pings in iter_rra_rows(lines, rra.index, meta):
            if ts in seen:
                continue
            seen.add(ts)
            yield ts, pings


def dump_rrd(rrd_path: str) -> list[str]:
    """Run rrdtool dump on an RRD file, return output lines."""
    result = subprocess.run(
        ["rrdtool", "dump", rrd_path],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()
