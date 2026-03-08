"""
fping subprocess wrapper.

Runs: fping -C <count> -q -p <interval_ms> <host1> <host2> ...

fping -C output (stderr) looks like:
  8.8.8.8 : 12.34 11.23 - 13.01 ...
  1.1.1.1 : 10.00 9.99 10.01 ...

where '-' means packet loss.

Note: on macOS, intervals below ~100ms cause near-total loss due to kernel
ICMP rate limiting. 200ms is a safe default (20 pings × 200ms = 4s per cycle).
"""

from __future__ import annotations

import asyncio
import re
from typing import Optional


def parse_fping_output(output: str, hosts: list[str]) -> dict[str, list[Optional[float]]]:
    """
    Parse fping -C output into a dict mapping host -> list of RTT values.

    Each RTT value is a float (ms) or None for packet loss.
    """
    results: dict[str, list[Optional[float]]] = {}

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        # Format: "<host> : <rtt1> <rtt2> ... "
        match = re.match(r'^(\S+)\s+:\s+(.+)$', line)
        if not match:
            continue

        host = match.group(1)
        rtt_str = match.group(2).strip()

        rtts: list[Optional[float]] = []
        for token in rtt_str.split():
            if token == '-':
                rtts.append(None)
            else:
                try:
                    rtts.append(float(token))
                except ValueError:
                    rtts.append(None)

        results[host] = rtts

    # Ensure all requested hosts are present (fill missing with all-loss)
    for host in hosts:
        if host not in results:
            results[host] = []

    return results


async def ping_hosts(
    hosts: list[str],
    count: int = 20,
    interval_ms: int = 200,
    timeout_ms: int = 2000,
) -> dict[str, list[Optional[float]]]:
    """
    Ping a list of hosts concurrently using fping.

    Returns dict mapping host -> list of RTT values (None = packet loss).
    Raises RuntimeError if fping is not found or returns a non-ping error.

    interval_ms: gap between successive pings to the same host. fping matches
                 responses by ICMP sequence number, so RTT > interval_ms is
                 fine — responses can come back out of order.
    timeout_ms:  how long fping waits for a response before counting it as
                 lost. Set generously (default 2000ms) to handle satellite
                 links and high-latency WAN paths.
    """
    if not hosts:
        return {}

    cmd = [
        "fping",
        "-C", str(count),  # count pings per host, output in -C format
        "-q",              # quiet (suppress per-ping output, use summary)
        "-p", str(interval_ms),  # interval between pings to same host (ms)
        "-t", str(timeout_ms),   # per-ping timeout (ms)
    ] + hosts

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
    except FileNotFoundError:
        raise RuntimeError(
            "fping not found. Install with: brew install fping"
        )

    # fping -C writes results to stderr (by design)
    output = stderr.decode("utf-8", errors="replace")

    return parse_fping_output(output, hosts)
