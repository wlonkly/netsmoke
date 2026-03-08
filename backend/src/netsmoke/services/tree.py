from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from netsmoke.config_loader import NetsmokeConfig, TargetNode, load_config


@dataclass(frozen=True, slots=True)
class TargetRecord:
    id: str
    name: str
    host: str
    path: str


@dataclass(frozen=True, slots=True)
class FolderRecord:
    id: str
    name: str
    path: str
    children: tuple['TreeNode', ...]


TreeNode = FolderRecord | TargetRecord



def slugify(value: str) -> str:
    normalized = ''.join(character.lower() if character.isalnum() else '-' for character in value)
    collapsed = '-'.join(part for part in normalized.split('-') if part)
    return collapsed or 'node'



def build_tree(config: NetsmokeConfig) -> tuple[TreeNode, ...]:
    return tuple(_build_node(node, ()) for node in config.targets)



def flatten_targets(config: NetsmokeConfig) -> list[TargetRecord]:
    flattened: list[TargetRecord] = []

    def walk(node: TreeNode) -> None:
        if isinstance(node, TargetRecord):
            flattened.append(node)
            return

        for child in node.children:
            walk(child)

    for root in build_tree(config):
        walk(root)

    return flattened



def _build_node(node: TargetNode, parents: tuple[str, ...]) -> TreeNode:
    path_parts = (*parents, node.name)
    path = '/'.join(path_parts)
    node_id = slugify(path)

    if node.type == 'host':
        return TargetRecord(id=node_id, name=node.name, host=node.host or '', path=path)

    children = tuple(_build_node(child, path_parts) for child in node.children)
    return FolderRecord(id=node_id, name=node.name, path=path, children=children)


@lru_cache(maxsize=8)
def get_config(config_path: Path) -> NetsmokeConfig:
    return load_config(config_path)


@lru_cache(maxsize=8)
def get_tree(config_path: Path) -> tuple[TreeNode, ...]:
    return build_tree(get_config(config_path))


@lru_cache(maxsize=8)
def get_flat_targets(config_path: Path) -> tuple[TargetRecord, ...]:
    return tuple(flatten_targets(get_config(config_path)))
