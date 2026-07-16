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
        indices = _peak_preserving_indices(indices, values, max_points)
    return values[indices], depth[indices]


def _peak_preserving_indices(
    indices: NDArray[np.int64], values: NDArray[np.float64], max_points: int
) -> NDArray[np.int64]:
    if max_points == 2:
        return indices[[0, -1]]
    interior = indices[1:-1]
    bucket_count = max(1, (max_points - 2) // 2)
    selected = [int(indices[0]), int(indices[-1])]
    for bucket in np.array_split(interior, bucket_count):
        if bucket.size == 0:
            continue
        bucket_values = values[bucket]
        selected.extend(
            (int(bucket[int(np.argmin(bucket_values))]), int(bucket[int(np.argmax(bucket_values))]))
        )
    return np.asarray(sorted(set(selected)), dtype=np.int64)
