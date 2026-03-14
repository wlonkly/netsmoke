"""Tests for config.py"""

import textwrap
from pathlib import Path

import pytest
import yaml

from netsmoke.config import (
    Config,
    Folder,
    Target,
    load_config,
    target_full_path,
    tree_to_json,
)


def _write_config(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def test_load_flat_targets(tmp_path):
    cfg_path = _write_config(tmp_path, """
        settings:
          ping_count: 10
          ping_interval: 30
        targets:
          - name: "Google DNS"
            host: "8.8.8.8"
          - name: "Cloudflare DNS"
            host: "1.1.1.1"
    """)
    config = load_config(cfg_path)

    assert config.ping_count == 10
    assert config.ping_interval == 30
    assert len(config.all_targets) == 2
    assert len(config.tree) == 2

    google = config.all_targets[0]
    assert google.name == "Google DNS"
    assert google.host == "8.8.8.8"
    assert google.folder_path == ""


def test_load_nested_folders(tmp_path):
    cfg_path = _write_config(tmp_path, """
        settings:
          ping_count: 20
          ping_interval: 60
        targets:
          - folder: "CDNs"
            targets:
              - name: "Cloudflare"
                host: "1.1.1.1"
              - name: "Quad9"
                host: "9.9.9.9"
          - folder: "Local"
            targets:
              - name: "Gateway"
                host: "192.168.1.1"
              - folder: "Servers"
                targets:
                  - name: "Server1"
                    host: "192.168.1.10"
    """)
    config = load_config(cfg_path)

    # All targets flattened
    paths = {target_full_path(t) for t in config.all_targets}
    assert "CDNs/Cloudflare" in paths
    assert "CDNs/Quad9" in paths
    assert "Local/Gateway" in paths
    assert "Local/Servers/Server1" in paths
    assert len(config.all_targets) == 4


def test_target_full_path_root():
    t = Target(name="Google DNS", host="8.8.8.8", folder_path="")
    assert target_full_path(t) == "Google DNS"


def test_target_full_path_nested():
    t = Target(name="Cloudflare", host="1.1.1.1", folder_path="CDNs")
    assert target_full_path(t) == "CDNs/Cloudflare"


def test_tree_to_json(tmp_path):
    cfg_path = _write_config(tmp_path, """
        settings:
          ping_count: 20
          ping_interval: 60
        targets:
          - name: "Root Target"
            host: "1.2.3.4"
          - folder: "Folder1"
            targets:
              - name: "Child"
                host: "5.6.7.8"
    """)
    config = load_config(cfg_path)
    tree = tree_to_json(config.tree)

    assert tree[0]["type"] == "target"
    assert tree[0]["name"] == "Root Target"
    assert tree[0]["path"] == "Root Target"

    assert tree[1]["type"] == "folder"
    assert tree[1]["name"] == "Folder1"
    children = tree[1]["children"]
    assert len(children) == 1
    assert children[0]["type"] == "target"
    assert children[0]["path"] == "Folder1/Child"


def test_defaults_when_settings_missing(tmp_path):
    cfg_path = _write_config(tmp_path, """
        targets:
          - name: "X"
            host: "1.1.1.1"
    """)
    config = load_config(cfg_path)
    assert config.ping_count == 20
    assert config.ping_interval == 60


def test_invalid_item_raises(tmp_path):
    cfg_path = _write_config(tmp_path, """
        targets:
          - bad_key: "oops"
    """)
    with pytest.raises(ValueError, match="Invalid config item"):
        load_config(cfg_path)
