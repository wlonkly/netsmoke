"""
Async background collector loop.

Reads all targets from config, pings them every `ping_interval` seconds,
and stores results in the SQLite database.
"""

from __future__ import annotations

import asyncio
import logging
import time

import aiosqlite

from netsmoke.config import Config, target_full_path
from netsmoke.db import insert_samples
from netsmoke.pinger import ping_hosts

logger = logging.getLogger(__name__)


async def run_collector(config: Config, db: aiosqlite.Connection) -> None:
    """
    Main collector loop. Runs forever until cancelled.

    Pings all targets every `config.ping_interval` seconds.
    """
    logger.info(
        "Collector started: %d targets, interval=%ds, count=%d",
        len(config.all_targets),
        config.ping_interval,
        config.ping_count,
    )

    while True:
        start = time.monotonic()
        await _collect_once(config, db)
        elapsed = time.monotonic() - start
        sleep_time = max(0.0, config.ping_interval - elapsed)
        logger.debug("Collection done in %.1fs, sleeping %.1fs", elapsed, sleep_time)
        await asyncio.sleep(sleep_time)


async def _collect_once(config: Config, db: aiosqlite.Connection) -> None:
    """Run one round of pings for all targets and store results."""
    hosts = [t.host for t in config.all_targets]
    if not hosts:
        return

    timestamp = int(time.time())

    try:
        results = await ping_hosts(hosts, count=config.ping_count)
    except RuntimeError as e:
        logger.error("Ping failed: %s", e)
        return

    # Map host → target path
    host_to_path: dict[str, str] = {
        t.host: target_full_path(t) for t in config.all_targets
    }

    for target in config.all_targets:
        path = target_full_path(target)
        rtts = results.get(target.host, [])

        if not rtts:
            # All loss — store all-None samples
            rtts = [None] * config.ping_count

        try:
            await insert_samples(db, path, timestamp, rtts)
            logger.debug("Stored %d samples for %s", len(rtts), path)
        except Exception as e:
            logger.error("Failed to store samples for %s: %s", path, e)
