"""
CLI entry point for smokeping-import.

Usage:
    smokeping-import \
        --data-dir /path/to/smokeping/data \
        --targets-file /path/to/smokeping/config/Targets \
        --db ../netsmoke.db \
        --config ../config.yaml
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml


def _check_rrdtool() -> None:
    if shutil.which("rrdtool") is None:
        sys.exit(
            "error: rrdtool not found in PATH.  Install it with: brew install rrdtool"
        )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="smokeping-import",
        description="Import SmokePing RRD data into a netsmoke SQLite database.",
    )
    p.add_argument(
        "--data-dir",
        required=True,
        metavar="PATH",
        help="SmokePing data/ directory containing .rrd files",
    )
    p.add_argument(
        "--targets-file",
        metavar="PATH",
        default=None,
        help="SmokePing Targets config file (optional; config.yaml won't be written if omitted)",
    )
    p.add_argument(
        "--db",
        default="./netsmoke.db",
        metavar="PATH",
        help="Output SQLite path (default: ./netsmoke.db)",
    )
    p.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="Output config.yaml path (default: print to stdout)",
    )
    p.add_argument(
        "--ping-interval",
        type=int,
        default=300,
        metavar="INT",
        help="ping_interval value in generated config.yaml (default: 300)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count rows but do not write to DB or config file",
    )
    return p


def main() -> None:
    _check_rrdtool()

    args = _build_parser().parse_args()

    data_dir = args.data_dir
    targets_file = args.targets_file
    db_path = args.db
    config_path = args.config
    ping_interval = args.ping_interval
    dry_run = args.dry_run

    if dry_run:
        print("[dry-run] no writes will be performed")

    # --- Parse targets file (optional) ---
    targets_by_path: dict[str, object] = {}
    config_tree = None
    if targets_file:
        from .targets_parser import (
            ParsedTarget,
            collect_all_targets,
            parse_targets_file,
            tree_to_yaml_dict,
        )

        print(f"Parsing targets file: {targets_file}")
        config_tree = parse_targets_file(targets_file)
        all_targets = collect_all_targets(config_tree)
        for t in all_targets:
            key = f"{t.folder_path}/{t.name}".lstrip("/")
            targets_by_path[key] = t
        print(f"  found {len(all_targets)} target(s) in config")

    # --- Find RRD files ---
    from .importer import find_rrd_files, open_db

    rrd_files = find_rrd_files(data_dir)
    if not rrd_files:
        sys.exit(f"error: no .rrd files found under {data_dir}")
    print(f"\nFound {len(rrd_files)} RRD file(s) under {data_dir}\n")

    # --- Open DB ---
    db = None
    if not dry_run:
        print(f"Opening DB: {db_path}")
        db = open_db(db_path)

    # --- Import each RRD ---
    from .importer import import_rrd

    orphaned: list[str] = []
    grand_total_ts = 0
    grand_total_rows = 0

    for rrd_path, target_path in rrd_files:
        print(f"Importing {target_path}...")
        stats = import_rrd(db, rrd_path, target_path, dry_run=dry_run)

        if stats.get("skipped"):
            print(f"  SKIPPED: {stats.get('reason')}")
            continue

        for arch in stats.get("archive_stats", []):
            label = f"{arch['step']}s"
            print(
                f"  archive {label:>8}: {arch['total']:>6} timestamps"
                + (f" ({arch['new']} new)" if arch["new"] != arch["total"] else "")
            )

        total_ts = stats["total_timestamps"]
        total_rows = stats["total_rows"]
        print(
            f"  total: {total_ts} timestamps → {total_rows:,} rows"
            f"  [{stats['start_date']} → {stats['end_date']}]"
        )

        grand_total_ts += total_ts
        grand_total_rows += total_rows

        if targets_file and target_path not in targets_by_path:
            orphaned.append(target_path)

    # --- Backfill rollups ---
    if not dry_run and db is not None:
        from .importer import backfill_rollups

        ping_count = _detect_ping_count(rrd_files) if rrd_files else 20
        print("\nBuilding rollup aggregates (1mo/1y graphs)...")
        rollup_stats = backfill_rollups(db, ping_count)
        print(
            f"  {rollup_stats['targets']} target(s) → "
            f"{rollup_stats['hour_buckets']:,} hour buckets, "
            f"{rollup_stats['day_buckets']:,} day buckets"
        )

    # --- Summary ---
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Import complete:")
    print(f"  {len(rrd_files)} RRD files → {grand_total_ts:,} timestamps → {grand_total_rows:,} rows")

    if orphaned:
        print(f"\nWarning: {len(orphaned)} RRD file(s) have no matching Targets entry:")
        for p in orphaned:
            print(f"  {p}")
        print("  These targets were imported into the DB but will not appear in config.yaml.")

    # --- Write config.yaml ---
    if targets_file and config_tree is not None:
        from .targets_parser import tree_to_yaml_dict

        # ping_count: SmokePing default is 20; detect from first RRD if we can
        ping_count = _detect_ping_count(rrd_files) if rrd_files else 20

        config_dict = tree_to_yaml_dict(config_tree, ping_count, ping_interval)
        yaml_text = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

        if dry_run:
            print("\n[dry-run] config.yaml would be written as:\n")
            print(yaml_text)
        elif config_path:
            Path(config_path).write_text(yaml_text)
            print(f"\nWrote config.yaml → {config_path}")
        else:
            print("\n--- config.yaml ---")
            print(yaml_text)

    if db is not None:
        db.close()


def _detect_ping_count(rrd_files: list[tuple[str, str]]) -> int:
    """Peek at the first RRD file to count ping DS entries."""
    from .rrd_parser import dump_rrd, parse_rrd_header

    rrd_path, _ = rrd_files[0]
    try:
        lines = dump_rrd(rrd_path)
        meta = parse_rrd_header(lines)
        return meta.ping_count or 20
    except Exception:
        return 20
