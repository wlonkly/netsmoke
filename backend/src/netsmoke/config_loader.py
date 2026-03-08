from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


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
