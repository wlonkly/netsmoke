"""
Parse a SmokePing Targets config file into a netsmoke config.yaml structure.

SmokePing uses a +/++/+++ depth-prefix convention for its config sections.
A section with a `host` key is a terminal target; without it, it is a folder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedTarget:
    name: str
    host: str
    folder_path: str  # e.g. "Internet" or "Internet/CDNs"


@dataclass
class ParsedFolder:
    name: str
    folder_path: str
    children: list[ParsedTarget | ParsedFolder] = field(default_factory=list)


# Matches section headers like "+ Internet" or "++ Google"
SECTION_RE = re.compile(r'^(\++)\s+(\S+)')
# Matches key = value lines
KV_RE = re.compile(r'^(\w+)\s*=\s*(.*)')


def parse_targets_file(path: str) -> list[ParsedTarget | ParsedFolder]:
    """
    Parse a SmokePing Targets file.

    Returns a tree of ParsedFolder / ParsedTarget objects mirroring
    the SmokePing hierarchy.
    """
    with open(path) as f:
        lines = f.readlines()

    # Stack entries: (depth: int, name: str | None, children: list)
    # The first entry is a virtual root at depth 0.
    root_children: list[ParsedTarget | ParsedFolder] = []
    stack: list[tuple[int, str | None, list]] = [(0, None, root_children)]

    # State for the section currently being parsed (not yet flushed to tree)
    pending_depth: int | None = None
    pending_name: str | None = None
    pending_kv: dict[str, str] = {}

    def _flush() -> None:
        """Commit the pending section into the tree."""
        nonlocal pending_depth, pending_name, pending_kv
        if pending_name is None:
            return

        depth = pending_depth
        name = pending_name
        kv = pending_kv

        host = kv.get("host", "").strip()

        # Build folder_path from current stack (skip virtual root at index 0)
        fp_parts = [e[1] for e in stack if e[1] is not None]
        folder_path = "/".join(fp_parts)

        if host:
            node: ParsedTarget | ParsedFolder = ParsedTarget(
                name=name, host=host, folder_path=folder_path
            )
        else:
            child_path = f"{folder_path}/{name}".lstrip("/")
            node = ParsedFolder(name=name, folder_path=child_path)

        # Append to the innermost children list on the stack
        stack[-1][2].append(node)

        # If this is a folder, push it so its children attach here
        if isinstance(node, ParsedFolder):
            stack.append((depth, name, node.children))

        pending_depth = None
        pending_name = None
        pending_kv = {}

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        m_sec = SECTION_RE.match(line)
        if m_sec:
            new_depth = len(m_sec.group(1))
            new_name = m_sec.group(2)

            # Flush whatever was pending before opening new section
            _flush()

            # Pop the stack back so the top entry is the parent of new_depth
            # Parent depth = new_depth - 1; pop entries with depth >= new_depth
            while len(stack) > 1 and stack[-1][0] >= new_depth:
                stack.pop()

            pending_depth = new_depth
            pending_name = new_name
            pending_kv = {}
            continue

        m_kv = KV_RE.match(line)
        if m_kv and pending_name is not None:
            pending_kv[m_kv.group(1)] = m_kv.group(2).strip()

    # Flush the last pending section
    _flush()

    return root_children


def collect_all_targets(
    tree: list[ParsedTarget | ParsedFolder],
) -> list[ParsedTarget]:
    """Flatten a target tree into a list of all ParsedTarget objects."""
    result: list[ParsedTarget] = []
    for node in tree:
        if isinstance(node, ParsedTarget):
            result.append(node)
        else:
            result.extend(collect_all_targets(node.children))
    return result


def tree_to_yaml_dict(
    tree: list[ParsedTarget | ParsedFolder],
    ping_count: int,
    ping_interval: int,
) -> dict[str, Any]:
    """Convert parsed tree to a dict that yaml.dump() will render as valid config.yaml."""

    def _node(n: ParsedTarget | ParsedFolder) -> dict[str, Any]:
        if isinstance(n, ParsedTarget):
            return {"name": n.name, "host": n.host}
        else:
            return {
                "folder": n.name,
                "targets": [_node(c) for c in n.children],
            }

    return {
        "settings": {
            "ping_count": ping_count,
            "ping_interval": ping_interval,
        },
        "targets": [_node(n) for n in tree],
    }
