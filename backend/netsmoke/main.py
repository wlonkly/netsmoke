"""
netsmoke entry point.

Sets env vars for config/db paths and launches uvicorn. The FastAPI lifespan
in api.py handles collector startup and database open/close.
"""

from __future__ import annotations

import argparse
import logging
import os

import uvicorn


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="netsmoke — SmokePing-inspired network latency monitor"
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to YAML config file (default: config.yaml)",
    )
    parser.add_argument(
        "--db",
        default="netsmoke.db",
        help="Path to SQLite database file (default: netsmoke.db)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind API server (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind API server (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on Python file changes (dev mode)",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log level (default: info)",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    # Pass config/db paths to the lifespan via env vars.
    # Using absolute paths so reload workers find the files regardless of cwd.
    os.environ["NETSMOKE_CONFIG"] = os.path.abspath(args.config)
    os.environ["NETSMOKE_DB"] = os.path.abspath(args.db)

    uvicorn.run(
        "netsmoke.api:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
        reload_dirs=["netsmoke"] if args.reload else None,
    )


if __name__ == "__main__":
    main()
