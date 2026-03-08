from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


def _slugify(value: str) -> str:
    normalized = ''.join(character.lower() if character.isalnum() else '-' for character in value)
    collapsed = '-'.join(part for part in normalized.split('-') if part)
    return collapsed or 'node'


class ProbeDefaults(BaseModel):
    step_seconds: int = 300
    pings: int = 20
    timeout_seconds: float = 1.0
    packet_size_bytes: int = 56


class TargetNode(BaseModel):
    name: str
    type: Literal['folder', 'host']
    host: str | None = None
    children: list['TargetNode'] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_shape(self) -> 'TargetNode':
        if self.type == 'folder' and self.host is not None:
            raise ValueError('folder nodes cannot define host')
        if self.type == 'host' and not self.host:
            raise ValueError('host nodes must define host')
        if self.type == 'host' and self.children:
            raise ValueError('host nodes cannot have children')
        return self


class NetsmokeConfig(BaseModel):
    defaults: ProbeDefaults = Field(default_factory=ProbeDefaults)
    targets: list[TargetNode]

    @model_validator(mode='after')
    def validate_unique_targets(self) -> 'NetsmokeConfig':
        seen_ids: set[str] = set()
        seen_paths: set[str] = set()

        def walk(node: TargetNode, parents: tuple[str, ...]) -> None:
            path_parts = (*parents, node.name)
            path = '/'.join(path_parts)
            if path in seen_paths:
                raise ValueError(f'duplicate target path: {path}')
            seen_paths.add(path)

            generated_id = _slugify(path)
            if generated_id in seen_ids:
                raise ValueError(f'duplicate target id: {generated_id}')
            seen_ids.add(generated_id)

            for child in node.children:
                walk(child, path_parts)

        for target in self.targets:
            walk(target, ())

        return self



def load_config(path: Path) -> NetsmokeConfig:
    resolved_path = resolve_config_path(path)
    raw = yaml.safe_load(resolved_path.read_text())
    return NetsmokeConfig.model_validate(raw)



def resolve_config_path(path: Path) -> Path:
    if path.exists():
        return path

    search_roots = [Path.cwd(), *Path(__file__).resolve().parents]
    candidates: list[Path] = []

    for root in search_roots:
        candidates.append(root / path.name)
        candidates.append(root / 'config' / path.name)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f'Config file not found: {path}')
