from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


MAX_RENDERED_POINTS = 5000


def select_visible_samples(
    depth: NDArray[np.float64],
    values: NDArray[np.float64],
    top: float,
    bottom: float,
    *,
    max_points: int = MAX_RENDERED_POINTS,
    positive_values_only: bool = False,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if depth.shape != values.shape:
        raise ValueError("Шкала глубины и значения кривой должны иметь одинаковую форму")
    if max_points < 2:
        raise ValueError("Для отрисовки требуется минимум две точки")
    visible_top, visible_bottom = sorted((top, bottom))
    valid = (
        np.isfinite(depth)
        & np.isfinite(values)
        & (depth >= visible_top)
        & (depth <= visible_bottom)
    )
    if positive_values_only:
        valid &= values > 0
    indices = np.flatnonzero(valid)
    if indices.size > max_points:
        positions = np.linspace(0, indices.size - 1, max_points, dtype=np.int64)
        indices = indices[positions]
    return values[indices], depth[indices]
