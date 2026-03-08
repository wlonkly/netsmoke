import numpy as np

from netsmoke.graphs.smoke import calculate_smoke_bands



def test_calculate_smoke_bands_returns_half_as_many_bands() -> None:
    samples = np.array([[10.0, 12.0, 13.0, 16.0], [9.0, 11.0, 14.0, 18.0]])

    bands = calculate_smoke_bands(samples)

    assert len(bands) == 2
    assert bands[0].color.startswith("#")
