"""
YAML config loader and target tree parser.
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Target:
    name: str
    host: str
    folder_path: str  # e.g. "" for root, "CDNs" for CDNs/Cloudflare


@dataclass
class Folder:
    name: str
    folder_path: str  # full path, e.g. "CDNs"
    targets: list[Target] = field(default_factory=list)
    subfolders: list[Folder] = field(default_factory=list)


@dataclass
class Config:
    ping_count: int
    ping_interval: int  # seconds
    # Flat list of all targets (for easy iteration by the collector)
    all_targets: list[Target] = field(default_factory=list)
    # Root-level tree (for sidebar rendering)
    tree: list[Target | Folder] = field(default_factory=list)


def _parse_targets(
    items: list[dict[str, Any]],
    parent_path: str,
    all_targets: list[Target],
) -> list[Target | Folder]:
    """Recursively parse targets/folders from a YAML list."""
    result: list[Target | Folder] = []

    for item in items:
        if "folder" in item:
            folder_name = item["folder"]
            folder_path = f"{parent_path}/{folder_name}" if parent_path else folder_name
            folder = Folder(name=folder_name, folder_path=folder_path)
            children = _parse_targets(item.get("targets", []), folder_path, all_targets)
            for child in children:
                if isinstance(child, Target):
                    folder.targets.append(child)
                else:
                    folder.subfolders.append(child)
            result.append(folder)
        elif "name" in item and "host" in item:
            target = Target(
                name=item["name"],
                host=item["host"],
                folder_path=parent_path,
            )
            all_targets.append(target)
            result.append(target)
        else:
            raise ValueError(f"Invalid config item (must have 'folder' or 'name'+'host'): {item}")

    return result


def load_config(path: str | Path) -> Config:
    """Load and parse netsmoke YAML config file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    settings = data.get("settings", {})
    ping_count = int(settings.get("ping_count", 20))
    ping_interval = int(settings.get("ping_interval", 60))

    all_targets: list[Target] = []
    tree = _parse_targets(data.get("targets", []), "", all_targets)

    return Config(
        ping_count=ping_count,
        ping_interval=ping_interval,
        all_targets=all_targets,
        tree=tree,
    )


def target_full_path(target: Target) -> str:
    """Return the URL-safe path for a target, e.g. 'CDNs/Cloudflare'."""
    if target.folder_path:
        return f"{target.folder_path}/{target.name}"
    return target.name


def tree_to_json(items: list[Target | Folder]) -> list[dict]:
    """Convert the target tree to a JSON-serializable structure."""
    result = []
    for item in items:
        if isinstance(item, Target):
            result.append({
                "type": "target",
                "name": item.name,
                "host": item.host,
                "path": target_full_path(item),
            })
        else:
            children = item.targets + item.subfolders  # type: ignore[operator]
            result.append({
                "type": "folder",
                "name": item.name,
                "path": item.folder_path,
                "children": tree_to_json(children),
            })
    return result
