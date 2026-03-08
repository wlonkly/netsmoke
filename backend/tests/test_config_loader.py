from pathlib import Path

from netsmoke.config_loader import load_config, resolve_config_path



def test_load_config(tmp_path: Path) -> None:
    config_file = tmp_path / 'netsmoke.yaml'
    config_file.write_text(
        '''
        defaults:
          step_seconds: 300
          pings: 20
        targets:
          - name: Core
            type: folder
            children:
              - name: gateway
                type: host
                host: 192.0.2.1
        '''
    )

    config = load_config(config_file)

    assert config.defaults.step_seconds == 300
    assert config.targets[0].children[0].host == '192.0.2.1'



def test_resolve_config_path_finds_repo_config_when_default_path_missing() -> None:
    resolved = resolve_config_path(Path('/app/config/netsmoke.yaml'))

    assert resolved.name == 'netsmoke.yaml'
    assert resolved.exists()
