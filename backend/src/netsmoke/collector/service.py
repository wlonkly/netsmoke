from collections.abc import Sequence
from datetime import UTC, datetime


class CollectorService:
    async def collect_once(self, targets: Sequence[dict[str, str]]) -> list[dict[str, object]]:
        observed_at = datetime.now(UTC)
        return [
            {
                "target": target,
                "observed_at": observed_at,
                "sent": 0,
                "received": 0,
                "loss_pct": 100.0,
                "median_rtt_ms": None,
            }
            for target in targets
        ]
