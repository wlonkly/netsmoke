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
    type: Literal["folder", "host"]
    host: str | None = None
    children: list["TargetNode"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shape(self) -> "TargetNode":
        if self.type == "folder" and self.host is not None:
            raise ValueError("folder nodes cannot define host")
        if self.type == "host" and not self.host:
            raise ValueError("host nodes must define host")
        if self.type == "host" and self.children:
            raise ValueError("host nodes cannot have children")
        return self


class NetsmokeConfig(BaseModel):
    defaults: ProbeDefaults = Field(default_factory=ProbeDefaults)
    targets: list[TargetNode]


def load_config(path: Path) -> NetsmokeConfig:
    raw = yaml.safe_load(path.read_text())
    return NetsmokeConfig.model_validate(raw)
