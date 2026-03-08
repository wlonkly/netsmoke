from dataclasses import dataclass
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
