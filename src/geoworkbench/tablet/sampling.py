from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


MAX_RENDERED_POINTS = 5000
_AXIS_GAP_FACTOR = 5.0
_VIEWPORT_CONTEXT_POINTS = 2


def snap_viewport_to_axis_samples(
    axis: NDArray[np.float64],
    top: float,
    bottom: float,
) -> tuple[float, float]:
    """Move an entirely empty viewport to the nearest recorded axis sample.

    GeoScape time series can contain long periods where acquisition was not
    running. Mapping a scrollbar linearly over the complete calendar interval
    allowed the user to stop inside such a period and see a completely empty
    tablet. The real timestamp gap is preserved, but navigation jumps to the
    closest recorded window instead of leaving the screen stranded in empty
    time.
    """

    visible_top, visible_bottom = sorted((float(top), float(bottom)))
    finite = np.asarray(axis, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0 or visible_bottom <= visible_top:
        return visible_top, visible_bottom
    finite.sort(kind="stable")
    start = int(np.searchsorted(finite, visible_top, side="left"))
    if start < finite.size and finite[start] <= visible_bottom:
        return visible_top, visible_bottom

    center = (visible_top + visible_bottom) / 2.0
    insertion = int(np.searchsorted(finite, center, side="left"))
    candidates: list[float] = []
    if insertion < finite.size:
        candidates.append(float(finite[insertion]))
    if insertion > 0:
        candidates.append(float(finite[insertion - 1]))
    if not candidates:
        return visible_top, visible_bottom
    nearest = min(candidates, key=lambda value: abs(value - center))
    span = visible_bottom - visible_top
    data_top = float(finite[0])
    data_bottom = float(finite[-1])
    if span >= data_bottom - data_top:
        return data_top, data_bottom
    snapped_top = nearest - span / 2.0
    snapped_top = max(data_top, min(snapped_top, data_bottom - span))
    return snapped_top, snapped_top + span


def select_visible_samples(
    depth: NDArray[np.float64],
    values: NDArray[np.float64],
    top: float,
    bottom: float,
    *,
    max_points: int = MAX_RENDERED_POINTS,
    positive_values_only: bool = False,
    include_viewport_context: bool = True,
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

    # Sort the complete finite axis first, then retain a small context margin on
    # both sides of the viewport.  Selecting only samples strictly inside the
    # visible interval made a continuous curve disappear whenever the viewport
    # landed between two source rows.  It also clipped the first and last line
    # segment on every wheel/scroll update.
    finite_axis = np.isfinite(depth)
    ordered_depth = np.asarray(depth[finite_axis], dtype=np.float64)
    ordered_values = np.asarray(values[finite_axis], dtype=np.float64).copy()
    if ordered_depth.size == 0:
        return ordered_values, ordered_depth

    # LAS/acquisition indexes are normally monotonic. Avoid allocating and
    # sorting an N-element permutation for every viewport update in that common
    # case; retain the stable-sort fallback for imported unsorted sources.
    is_monotonic = bool(
        ordered_depth.size < 2 or np.all(ordered_depth[1:] >= ordered_depth[:-1])
    )
    if not is_monotonic:
        order = np.argsort(ordered_depth, kind="stable")
        ordered_depth = ordered_depth[order]
        ordered_values = ordered_values[order]

    normal_step = _nominal_axis_step(ordered_depth)
    start = int(np.searchsorted(ordered_depth, visible_top, side="left"))
    stop = int(np.searchsorted(ordered_depth, visible_bottom, side="right"))
    if include_viewport_context:
        context_start = max(0, start - _VIEWPORT_CONTEXT_POINTS)
        context_stop = min(ordered_depth.size, stop + _VIEWPORT_CONTEXT_POINTS)
    elif start == stop:
        # Keep the segment crossing a viewport that falls between source rows.
        # Ordinary non-empty ranges remain exact so point counts and editing
        # boundaries describe only samples inside the requested interval.
        context_start = max(0, start - 1)
        context_stop = min(ordered_depth.size, stop + 1)
    else:
        context_start = start
        context_stop = stop
    selected_depth = ordered_depth[context_start:context_stop]
    selected_values = ordered_values[context_start:context_stop]
    if selected_depth.size == 0:
        return selected_values, selected_depth

    selected_values[~np.isfinite(selected_values)] = np.nan
    if positive_values_only:
        selected_values[selected_values <= 0.0] = np.nan

    selected_depth, selected_values = _collapse_duplicate_axis_samples(
        selected_depth, selected_values
    )
    selected_depth, selected_values = _insert_large_axis_gap_markers(
        selected_depth, selected_values, normal_step=normal_step
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
    axis: NDArray[np.float64],
    values: NDArray[np.float64],
    *,
    normal_step: float | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Insert one NaN point where a regular acquisition grid has a large hole."""
    if axis.size < 2:
        return axis, values
    deltas = np.diff(axis)
    if normal_step is None:
        normal_step = _nominal_axis_step(axis)
    if normal_step is None or not np.isfinite(normal_step) or normal_step <= 0.0:
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


def _nominal_axis_step(axis: NDArray[np.float64]) -> float | None:
    """Return the robust positive source step for gap classification."""

    if axis.size < 2:
        return None
    deltas = np.diff(axis)
    positive = deltas[np.isfinite(deltas) & (deltas > 0.0)]
    if positive.size == 0:
        return None
    step = float(np.median(positive))
    return step if np.isfinite(step) and step > 0.0 else None


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
