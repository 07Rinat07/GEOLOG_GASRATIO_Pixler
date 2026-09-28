from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray


def continuous_depth_segments(
    depth: NDArray[np.float64],
    indices: NDArray[np.int64],
    *,
    limit: int,
    gap_factor: float = 3.0,
) -> tuple[NDArray[np.int64], ...]:
    """Split sampled depth rows at real acquisition gaps before downsampling.

    The input indices must already be ordered by depth. Downsampling is applied
    independently inside every continuous run so rendering cannot bridge a
    missing depth interval merely because two remaining points are finite.
    """

    if limit < 2:
        raise ValueError("limit must be at least 2")
    if not math.isfinite(gap_factor) or gap_factor <= 1.0:
        raise ValueError("gap_factor must be finite and greater than 1")
    if indices.size == 0:
        return ()

    ordered_depth = np.asarray(depth[indices], dtype=np.float64)
    if ordered_depth.size == 1:
        return (indices.copy(),)
    differences = np.diff(ordered_depth)
    positive = differences[np.isfinite(differences) & (differences > 0.0)]
    if positive.size == 0:
        return (indices.copy(),)

    # Large acquisition gaps must not raise their own break threshold. Use the
    # lower half of positive steps to estimate the native sampling cadence.
    ordered_steps = np.sort(positive)
    typical_step = float(np.median(ordered_steps[: (len(ordered_steps) + 1) // 2]))
    large_steps = differences > typical_step * gap_factor
    # A sustained change in sampling cadence is a continuous coarse run, not
    # a series of missing intervals. Only isolated oversized steps are gaps.
    neighboring_large = np.zeros(large_steps.shape, dtype=np.bool_)
    neighboring_large[1:] |= large_steps[:-1]
    neighboring_large[:-1] |= large_steps[1:]
    gap_positions = np.flatnonzero(
        ~np.isfinite(differences) | (large_steps & ~neighboring_large)
    )
    raw_segments = np.split(indices, gap_positions + 1)
    raw_segments = [segment for segment in raw_segments if segment.size]
    total = sum(segment.size for segment in raw_segments)
    if total <= limit:
        return tuple(segment.copy() for segment in raw_segments)

    # Single points cannot form a line. Reserve both endpoints for each drawn
    # run, then assign the remaining point budget by run length.
    drawable = [segment for segment in raw_segments if segment.size >= 2]
    if not drawable:
        return ()
    if len(drawable) * 2 > limit:
        keep = np.linspace(0, len(drawable) - 1, limit // 2, dtype=np.int64)
        drawable = [drawable[int(index)] for index in keep]
    capacity = np.asarray([segment.size - 2 for segment in drawable], dtype=np.int64)
    extra_budget = min(limit - 2 * len(drawable), int(capacity.sum()))
    if extra_budget and capacity.sum():
        exact = capacity.astype(np.float64) * extra_budget / capacity.sum()
        extra = np.floor(exact).astype(np.int64)
        remainder = extra_budget - int(extra.sum())
        if remainder:
            candidates = np.argsort(-(exact - extra), kind="stable")
            extra[candidates[:remainder]] += 1
    else:
        extra = np.zeros(len(drawable), dtype=np.int64)
    return tuple(
        segment[np.linspace(0, segment.size - 1, 2 + int(count), dtype=np.int64)]
        for segment, count in zip(drawable, extra)
    )
