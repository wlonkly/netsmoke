from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class SmokeBand:
    bottom: np.ndarray
    height: np.ndarray
    color: str



def calculate_smoke_bands(samples: np.ndarray) -> list[SmokeBand]:
    sorted_samples = np.sort(np.where(np.isnan(samples), np.inf, samples), axis=1)
    half = samples.shape[1] // 2
    bands: list[SmokeBand] = []

    for lower_index in range(half):
        upper_index = samples.shape[1] - 1 - lower_index
        gray_value = int(190 / half * (half - lower_index)) + 50
        color = f"#{gray_value:02x}{gray_value:02x}{gray_value:02x}"
        bottom = sorted_samples[:, lower_index].copy()
        top = sorted_samples[:, upper_index].copy()
        missing = np.isinf(bottom) | np.isinf(top)
        bottom[missing] = np.nan
        top[missing] = np.nan
        bands.append(SmokeBand(bottom=bottom, height=top - bottom, color=color))

    return bands
