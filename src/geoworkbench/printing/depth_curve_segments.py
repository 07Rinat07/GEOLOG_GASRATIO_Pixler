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

    typical_step = float(np.median(positive))
    gap_positions = np.flatnonzero(
        ~np.isfinite(differences) | (differences > typical_step * gap_factor)
    )
    raw_segments = np.split(indices, gap_positions + 1)
    raw_segments = [segment for segment in raw_segments if segment.size]
    total = sum(segment.size for segment in raw_segments)
    if total <= limit:
        return tuple(segment.copy() for segment in raw_segments)

    stride = max(1, math.ceil(total / limit))
    sampled: list[NDArray[np.int64]] = []
    for segment in raw_segments:
        if segment.size <= 2:
            sampled.append(segment.copy())
            continue
        chosen = segment[::stride]
        if chosen[-1] != segment[-1]:
            chosen = np.concatenate((chosen, segment[-1:]))
        sampled.append(np.asarray(chosen, dtype=np.int64))
    return tuple(sampled)
