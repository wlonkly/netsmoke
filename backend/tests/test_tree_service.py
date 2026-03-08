from pathlib import Path

from netsmoke.services.tree import FolderRecord, get_flat_targets, get_tree, slugify



def test_slugify_collapses_non_alphanumeric() -> None:
    assert slugify('Managed / Internal / gateway') == 'managed-internal-gateway'



def test_tree_and_flat_targets_follow_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / 'netsmoke.yaml'
    config_file.write_text(
        '''
        targets:
          - name: Managed
            type: folder
            children:
              - name: Internal
                type: folder
                children:
                  - name: gateway
                    type: host
                    host: 192.0.2.1
                  - name: dns resolver
                    type: host
                    host: 192.0.2.53
        '''
    )

    tree = get_tree(config_file)
    flat_targets = get_flat_targets(config_file)

    assert len(tree) == 1
    assert isinstance(tree[0], FolderRecord)
    assert tree[0].children[0].path == 'Managed/Internal'
    assert [target.id for target in flat_targets] == [
        'managed-internal-gateway',
        'managed-internal-dns-resolver',
    ]
