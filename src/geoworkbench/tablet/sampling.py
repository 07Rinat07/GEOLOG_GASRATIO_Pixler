from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


MAX_RENDERED_POINTS = 5000
_AXIS_GAP_FACTOR = 5.0


def select_visible_samples(
    depth: NDArray[np.float64],
    values: NDArray[np.float64],
    top: float,
    bottom: float,
    *,
    max_points: int = MAX_RENDERED_POINTS,
    positive_values_only: bool = False,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Prepare one curve for screen rendering without inventing continuity.

    The LAS ``NULL`` sentinel is imported as ``NaN``.  A missing value is not a
    numeric zero and must create a visible break in the curve.  The old renderer
    removed all non-finite samples before plotting; consequently pyqtgraph saw
    only finite points and connected the last value before a data gap with the
    first value after it.  On a masterlog that looks like a curve appearing from
    nowhere.

    This function therefore keeps ``NaN`` separators, collapses repeated axis
    samples without converting an all-null group to zero, detects large holes in
    an otherwise regular depth/time grid, and downsamples each continuous segment
    independently.  A real numeric ``0`` remains a valid point on a linear scale.
    On a logarithmic scale non-positive values are represented as gaps because
    logarithm of zero or a negative value is undefined.
    """
    depth = np.asarray(depth, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    if depth.shape != values.shape:
        raise ValueError("Шкала глубины и значения кривой должны иметь одинаковую форму")
    if max_points < 2:
        raise ValueError("Для отрисовки требуется минимум две точки")

    visible_top, visible_bottom = sorted((float(top), float(bottom)))
    axis_mask = np.isfinite(depth) & (depth >= visible_top) & (depth <= visible_bottom)
    selected_depth = np.asarray(depth[axis_mask], dtype=np.float64)
    selected_values = np.asarray(values[axis_mask], dtype=np.float64).copy()
    if selected_depth.size == 0:
        return selected_values, selected_depth

    selected_values[~np.isfinite(selected_values)] = np.nan
    if positive_values_only:
        selected_values[selected_values <= 0.0] = np.nan

    order = np.argsort(selected_depth, kind="stable")
    if not np.array_equal(order, np.arange(order.size)):
        selected_depth = selected_depth[order]
        selected_values = selected_values[order]

    selected_depth, selected_values = _collapse_duplicate_axis_samples(
        selected_depth, selected_values
    )
    selected_depth, selected_values = _insert_large_axis_gap_markers(
        selected_depth, selected_values
    )
    if selected_depth.size <= max_points:
        return selected_values, selected_depth
    return _downsample_preserving_gaps(selected_depth, selected_values, max_points)


def _collapse_duplicate_axis_samples(
    axis: NDArray[np.float64], values: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Collapse duplicate depth/time rows while preserving missing-data state."""
    if axis.size < 2 or not np.any(axis[1:] == axis[:-1]):
        return axis, values

    unique_axis, starts, counts = np.unique(axis, return_index=True, return_counts=True)
    averaged_values = np.full(unique_axis.shape, np.nan, dtype=np.float64)
    for output_index, (start, count) in enumerate(zip(starts, counts, strict=True)):
        group = values[start : start + count]
        finite = group[np.isfinite(group)]
        if finite.size:
            averaged_values[output_index] = float(np.mean(finite))
    return unique_axis.astype(np.float64, copy=False), averaged_values


def _insert_large_axis_gap_markers(
    axis: NDArray[np.float64], values: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Insert one NaN point where a regular acquisition grid has a large hole."""
    if axis.size < 3:
        return axis, values
    deltas = np.diff(axis)
    positive = deltas[np.isfinite(deltas) & (deltas > 0.0)]
    if positive.size < 2:
        return axis, values
    normal_step = float(np.median(positive))
    if not np.isfinite(normal_step) or normal_step <= 0.0:
        return axis, values
    threshold = normal_step * _AXIS_GAP_FACTOR
    gap_indexes = np.flatnonzero(deltas > threshold)
    if gap_indexes.size == 0:
        return axis, values

    output_axis: list[float] = []
    output_values: list[float] = []
    gap_set = set(int(index) for index in gap_indexes)
    for index in range(axis.size - 1):
        output_axis.append(float(axis[index]))
        output_values.append(float(values[index]))
        if index in gap_set:
            output_axis.append(float((axis[index] + axis[index + 1]) / 2.0))
            output_values.append(float("nan"))
    output_axis.append(float(axis[-1]))
    output_values.append(float(values[-1]))
    return np.asarray(output_axis, dtype=np.float64), np.asarray(output_values, dtype=np.float64)


def _downsample_preserving_gaps(
    axis: NDArray[np.float64], values: NDArray[np.float64], max_points: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    finite = np.isfinite(values)
    segments = _finite_segments(finite)
    if not segments:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    separator_count = max(0, len(segments) - 1)
    minimum_per_segment = [1 if end - start == 1 else 2 for start, end in segments]
    minimum_total = sum(minimum_per_segment) + separator_count

    # Extremely fragmented data can contain more individual islands than the
    # render budget. Keep islands distributed over the whole viewport rather
    # than silently joining them or retaining only the shallow end.
    if minimum_total > max_points:
        keep_count = max(1, (max_points + 1) // 2)
        chosen = np.unique(
            np.linspace(0, len(segments) - 1, num=min(keep_count, len(segments)), dtype=int)
        )
        segments = [segments[int(index)] for index in chosen]
        budgets = [1] * len(segments)
    else:
        budgets = minimum_per_segment[:]
        remaining = max_points - minimum_total
        lengths = np.asarray([end - start for start, end in segments], dtype=np.float64)
        capacities = np.asarray(
            [max(0, int(length) - budget) for length, budget in zip(lengths, budgets, strict=True)],
            dtype=np.int64,
        )
        if remaining > 0 and int(np.sum(capacities)) > 0:
            weights = capacities / float(np.sum(capacities))
            extras = np.floor(weights * remaining).astype(np.int64)
            extras = np.minimum(extras, capacities)
            for index, extra in enumerate(extras):
                budgets[index] += int(extra)
            remaining -= int(np.sum(extras))
            while remaining > 0:
                candidates = [
                    index
                    for index, capacity in enumerate(capacities)
                    if budgets[index] < (segments[index][1] - segments[index][0])
                ]
                if not candidates:
                    break
                for index in candidates:
                    if remaining <= 0:
                        break
                    budgets[index] += 1
                    remaining -= 1

    output_axis: list[np.ndarray] = []
    output_values: list[np.ndarray] = []
    for segment_index, ((start, end), budget) in enumerate(zip(segments, budgets, strict=True)):
        segment_axis = axis[start:end]
        segment_values = values[start:end]
        if segment_axis.size > budget:
            positions = _peak_preserving_positions(segment_values, budget)
            segment_axis = segment_axis[positions]
            segment_values = segment_values[positions]
        if segment_index:
            previous_axis = output_axis[-1][-1]
            separator_axis = float((previous_axis + segment_axis[0]) / 2.0)
            output_axis.append(np.asarray([separator_axis], dtype=np.float64))
            output_values.append(np.asarray([np.nan], dtype=np.float64))
        output_axis.append(segment_axis)
        output_values.append(segment_values)

    return np.concatenate(output_values), np.concatenate(output_axis)


def _finite_segments(mask: NDArray[np.bool_]) -> list[tuple[int, int]]:
    padded = np.concatenate((np.asarray([False]), mask, np.asarray([False])))
    changes = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(changes == 1)
    ends = np.flatnonzero(changes == -1)
    return [(int(start), int(end)) for start, end in zip(starts, ends, strict=True)]


def _peak_preserving_positions(values: NDArray[np.float64], max_points: int) -> NDArray[np.int64]:
    count = values.size
    if count <= max_points:
        return np.arange(count, dtype=np.int64)
    if max_points <= 1:
        return np.asarray([int(np.argmax(np.abs(values)))], dtype=np.int64)
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
    selected_array = np.asarray(sorted(set(selected)), dtype=np.int64)
    if selected_array.size > max_points:
        selected_array = selected_array[
            np.linspace(0, selected_array.size - 1, num=max_points, dtype=int)
        ]
    return selected_array
