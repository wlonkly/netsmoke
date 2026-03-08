from pathlib import Path

from netsmoke.config_loader import load_config



def test_load_config(tmp_path: Path) -> None:
    config_file = tmp_path / "netsmoke.yaml"
    config_file.write_text(
        """
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
        """
    )

    config = load_config(config_file)

    assert config.defaults.step_seconds == 300
    assert config.targets[0].children[0].host == "192.0.2.1"
