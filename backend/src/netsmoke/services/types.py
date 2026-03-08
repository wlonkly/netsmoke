from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass(frozen=True, slots=True)
class CollectedRound:
    target_slug: str
    observed_at: datetime
    samples: tuple[float | None, ...]
    sent: int
    received: int
    loss_pct: float
    median_rtt_ms: float | None


@dataclass(frozen=True, slots=True)
class GraphSeries:
    timestamps: tuple[datetime, ...]
    samples: np.ndarray


@dataclass(frozen=True, slots=True)
class RecentMeasurement:
    observed_at: datetime
    sent: int
    received: int
    loss_pct: float
    median_rtt_ms: float | None


@dataclass(slots=True)
class CollectorRuntimeState:
    enabled: bool
    status: str = 'idle'
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    last_round_target_count: int = 0
    last_round_persisted_count: int = 0
    last_round_summary: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            'enabled': self.enabled,
            'status': self.status,
            'lastStartedAt': _to_iso(self.last_started_at),
            'lastFinishedAt': _to_iso(self.last_finished_at),
            'lastSuccessAt': _to_iso(self.last_success_at),
            'lastError': self.last_error,
            'lastErrorAt': _to_iso(self.last_error_at),
            'lastRoundTargetCount': self.last_round_target_count,
            'lastRoundPersistedCount': self.last_round_persisted_count,
            'lastRoundSummary': self.last_round_summary,
        }



def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
