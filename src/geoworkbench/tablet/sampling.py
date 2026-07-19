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
    """Prepare one curve for screen rendering in vertical-axis order.

    Rendering is intentionally independent from the raw LAS arrays. Reversed axes
    are sorted for display and repeated depth/time samples are averaged into one
    screen point. This prevents the long horizontal strokes that appear when many
    acquisition samples share the same mapped depth.
    """
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

    selected_depth = np.asarray(depth[valid], dtype=np.float64)
    selected_values = np.asarray(values[valid], dtype=np.float64)
    if selected_depth.size == 0:
        return selected_values, selected_depth

    order = np.argsort(selected_depth, kind="stable")
    if not np.array_equal(order, np.arange(order.size)):
        selected_depth = selected_depth[order]
        selected_values = selected_values[order]

    selected_depth, selected_values = _collapse_duplicate_axis_samples(
        selected_depth, selected_values
    )
    if selected_depth.size > max_points:
        positions = _peak_preserving_positions(selected_values, max_points)
        selected_depth = selected_depth[positions]
        selected_values = selected_values[positions]
    return selected_values, selected_depth


def _collapse_duplicate_axis_samples(
    axis: NDArray[np.float64], values: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if axis.size < 2 or not np.any(axis[1:] == axis[:-1]):
        return axis, values
    unique_axis, starts, counts = np.unique(
        axis, return_index=True, return_counts=True
    )
    sums = np.add.reduceat(values, starts)
    averaged_values = sums / counts
    return unique_axis.astype(np.float64, copy=False), averaged_values.astype(
        np.float64, copy=False
    )


def _peak_preserving_positions(
    values: NDArray[np.float64], max_points: int
) -> NDArray[np.int64]:
    count = values.size
    if count <= max_points:
        return np.arange(count, dtype=np.int64)
    if max_points == 2:
        return np.asarray([0, count - 1], dtype=np.int64)

    interior = np.arange(1, count - 1, dtype=np.int64)
    bucket_count = max(1, (max_points - 2) // 2)
    selected = [0, count - 1]
    for bucket in np.array_split(interior, bucket_count):
        if bucket.size == 0:
            continue
        bucket_values = values[bucket]
        selected.extend(
            (
                int(bucket[int(np.argmin(bucket_values))]),
                int(bucket[int(np.argmax(bucket_values))]),
            )
        )
    return np.asarray(sorted(set(selected)), dtype=np.int64)
