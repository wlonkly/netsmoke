from collections.abc import Sequence


class FPingProbe:
    async def run(self, hosts: Sequence[str]) -> dict[str, list[float | None]]:
        raise NotImplementedError("fping integration will be implemented after scaffolding")
