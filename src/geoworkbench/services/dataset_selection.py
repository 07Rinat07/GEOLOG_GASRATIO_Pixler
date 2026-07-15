from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import Dataset


def depth_interval_indices(
    dataset: Dataset, depth_top: float, depth_bottom: float
) -> NDArray[np.int64]:
    if not np.isfinite(depth_top) or not np.isfinite(depth_bottom):
        raise ValueError("Границы интервала должны быть конечными")
    if depth_top > depth_bottom:
        raise ValueError("Кровля интервала должна быть не глубже подошвы")
    depth = dataset.depth
    indices = np.flatnonzero(
        np.isfinite(depth) & (depth >= depth_top) & (depth <= depth_bottom)
    ).astype(np.int64)
    if indices.size == 0:
        raise ValueError("В выбранном глубинном интервале нет отсчётов")
    return indices
