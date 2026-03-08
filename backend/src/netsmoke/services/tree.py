from netsmoke.config_loader import NetsmokeConfig, TargetNode



def flatten_targets(config: NetsmokeConfig) -> list[dict[str, str]]:
    flattened: list[dict[str, str]] = []

    def walk(node: TargetNode, parents: list[str]) -> None:
        path = [*parents, node.name]
        if node.type == "host":
            flattened.append(
                {
                    "slug": "-".join(part.lower().replace(" ", "-") for part in path),
                    "name": node.name,
                    "host": node.host or "",
                    "path": "/".join(path),
                }
            )
            return

        for child in node.children:
            walk(child, path)

    for target in config.targets:
        walk(target, [])

    return flattened
