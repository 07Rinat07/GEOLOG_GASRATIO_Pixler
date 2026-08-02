from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from geoworkbench.calculations.curve_continuity import nominal_axis_step


FloatArray = NDArray[np.float64]
_AXIS_GAP_FACTOR = 5.0
_VIEWPORT_CONTEXT_POINTS = 2


def select_derived_gas_samples(
    axis: FloatArray,
    values: FloatArray,
    top: float,
    bottom: float,
    *,
    max_points: int,
    positive_values_only: bool,
) -> tuple[FloatArray, FloatArray]:
    """Prepare sparse Gas Ratio/Pixler/Haworth geometry for rendering.

    Derived gas channels are event-like calculations. Intermediate NULL rows,
    and non-positive values that cannot be represented on a logarithmic scale,
    are not independent acquisition outages. They are therefore omitted from
    the display geometry and neighbouring finite calculations remain connected.

    A separator is inserted only when the *source vertical axis itself* contains
    a real acquisition hole. The imported Dataset is never mutated; this is a
    viewport-only representation policy.
    """

    source_axis = np.asarray(axis, dtype=np.float64)
    source_values = np.asarray(values, dtype=np.float64)
    if source_axis.ndim != 1 or source_values.ndim != 1:
        raise ValueError("Шкала и значения производной газовой кривой должны быть одномерными")
    if source_axis.shape != source_values.shape:
        raise ValueError("Шкала и значения производной газовой кривой имеют разную длину")
    if max_points < 2:
        raise ValueError("Для отрисовки требуется минимум две точки")

    finite_axis = np.isfinite(source_axis)
    ordered_axis = source_axis[finite_axis]
    ordered_values = source_values[finite_axis]
    if ordered_axis.size == 0:
        return ordered_values.astype(np.float64, copy=True), ordered_axis.astype(
            np.float64, copy=True
        )

    if ordered_axis.size > 1 and not np.all(ordered_axis[1:] >= ordered_axis[:-1]):
        order = np.argsort(ordered_axis, kind="stable")
        ordered_axis = ordered_axis[order]
        ordered_values = ordered_values[order]

    source_outages = _source_axis_outages(ordered_axis)
    valid_updates = np.isfinite(ordered_values)
    if positive_values_only:
        valid_updates &= ordered_values > 0.0
    update_axis = ordered_axis[valid_updates]
    update_values = ordered_values[valid_updates]
    if update_axis.size == 0:
        return update_values.astype(np.float64, copy=True), update_axis.astype(
            np.float64, copy=True
        )

    update_axis, update_values = _collapse_duplicate_axis_samples(
        update_axis.astype(np.float64, copy=False),
        update_values.astype(np.float64, copy=False),
    )

    visible_top, visible_bottom = sorted((float(top), float(bottom)))
    start = int(np.searchsorted(update_axis, visible_top, side="left"))
    stop = int(np.searchsorted(update_axis, visible_bottom, side="right"))
    context_start = max(0, start - _VIEWPORT_CONTEXT_POINTS)
    context_stop = min(update_axis.size, stop + _VIEWPORT_CONTEXT_POINTS)
    selected_axis = update_axis[context_start:context_stop]
    selected_values = update_values[context_start:context_stop]
    if selected_axis.size == 0:
        return selected_values, selected_axis

    selected_axis, selected_values = _insert_source_outage_markers(
        selected_axis,
        selected_values,
        source_outages,
    )
    if selected_axis.size <= max_points:
        return selected_values, selected_axis
    return _downsample_preserving_segments(
        selected_axis,
        selected_values,
        max_points=max_points,
    )


def _source_axis_outages(axis: FloatArray) -> tuple[tuple[float, float], ...]:
    if axis.size < 2:
        return ()
    step = nominal_axis_step(axis)
    if step is None or not np.isfinite(step) or step <= 0.0:
        return ()
    threshold = float(step) * _AXIS_GAP_FACTOR
    indexes = np.flatnonzero(np.diff(axis) > threshold)
    return tuple((float(axis[index]), float(axis[index + 1])) for index in indexes)


def _collapse_duplicate_axis_samples(
    axis: FloatArray,
    values: FloatArray,
) -> tuple[FloatArray, FloatArray]:
    if axis.size < 2 or not np.any(axis[1:] == axis[:-1]):
        return axis, values
    unique_axis, starts, counts = np.unique(
        axis,
        return_index=True,
        return_counts=True,
    )
    averaged = np.full(unique_axis.shape, np.nan, dtype=np.float64)
    for output_index, (start, count) in enumerate(zip(starts, counts, strict=True)):
        group = values[start : start + count]
        finite = group[np.isfinite(group)]
        if finite.size:
            averaged[output_index] = float(np.mean(finite))
    return unique_axis.astype(np.float64, copy=False), averaged


def _insert_source_outage_markers(
    axis: FloatArray,
    values: FloatArray,
    outages: tuple[tuple[float, float], ...],
) -> tuple[FloatArray, FloatArray]:
    if axis.size < 2 or not outages:
        return axis, values

    output_axis: list[float] = []
    output_values: list[float] = []
    outage_index = 0
    for index in range(axis.size - 1):
        left = float(axis[index])
        right = float(axis[index + 1])
        output_axis.append(left)
        output_values.append(float(values[index]))
        while outage_index < len(outages) and outages[outage_index][1] <= left:
            outage_index += 1
        if outage_index < len(outages):
            outage_left, outage_right = outages[outage_index]
            if left <= outage_left and outage_right <= right:
                output_axis.append((outage_left + outage_right) / 2.0)
                output_values.append(float("nan"))
    output_axis.append(float(axis[-1]))
    output_values.append(float(values[-1]))
    return (
        np.asarray(output_axis, dtype=np.float64),
        np.asarray(output_values, dtype=np.float64),
    )


def _finite_segments(mask: NDArray[np.bool_]) -> list[tuple[int, int]]:
    padded = np.concatenate((np.asarray([False]), mask, np.asarray([False])))
    changes = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(changes == 1)
    ends = np.flatnonzero(changes == -1)
    return [(int(start), int(end)) for start, end in zip(starts, ends, strict=True)]


def _peak_positions(values: FloatArray, budget: int) -> NDArray[np.int64]:
    count = values.size
    if count <= budget:
        return np.arange(count, dtype=np.int64)
    if budget <= 1:
        return np.asarray([int(np.argmax(np.abs(values)))], dtype=np.int64)
    if budget == 2:
        return np.asarray([0, count - 1], dtype=np.int64)

    selected: list[int] = [0, count - 1]
    interior = np.arange(1, count - 1, dtype=np.int64)
    bucket_count = max(1, (budget - 2) // 2)
    for bucket in np.array_split(interior, bucket_count):
        if bucket.size == 0:
            continue
        bucket_values = values[bucket]
        selected.append(int(bucket[int(np.argmin(bucket_values))]))
        selected.append(int(bucket[int(np.argmax(bucket_values))]))
    positions = np.asarray(sorted(set(selected)), dtype=np.int64)
    if positions.size > budget:
        keep = np.linspace(0, positions.size - 1, num=budget, dtype=np.int64)
        positions = positions[keep]
    return positions


def _downsample_preserving_segments(
    axis: FloatArray,
    values: FloatArray,
    *,
    max_points: int,
) -> tuple[FloatArray, FloatArray]:
    segments = _finite_segments(np.isfinite(values))
    if not segments:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    separator_count = max(0, len(segments) - 1)
    available = max(1, max_points - separator_count)
    lengths = np.asarray([end - start for start, end in segments], dtype=np.float64)
    total = float(np.sum(lengths))
    budgets = [
        max(1, min(end - start, round(available * (end - start) / total)))
        for start, end in segments
    ]
    while sum(budgets) > available:
        candidate = max(
            (index for index, budget in enumerate(budgets) if budget > 1),
            key=lambda index: budgets[index],
            default=None,
        )
        if candidate is None:
            break
        budgets[candidate] -= 1
    while sum(budgets) < available:
        candidate = max(
            (
                index
                for index, ((start, end), budget) in enumerate(
                    zip(segments, budgets, strict=True)
                )
                if budget < end - start
            ),
            key=lambda index: lengths[index] - budgets[index],
            default=None,
        )
        if candidate is None:
            break
        budgets[candidate] += 1

    output_axis: list[FloatArray] = []
    output_values: list[FloatArray] = []
    for segment_index, ((start, end), budget) in enumerate(
        zip(segments, budgets, strict=True)
    ):
        segment_axis = axis[start:end]
        segment_values = values[start:end]
        positions = _peak_positions(segment_values, budget)
        if segment_index:
            separator = (float(output_axis[-1][-1]) + float(segment_axis[0])) / 2.0
            output_axis.append(np.asarray([separator], dtype=np.float64))
            output_values.append(np.asarray([np.nan], dtype=np.float64))
        output_axis.append(segment_axis[positions])
        output_values.append(segment_values[positions])
    return np.concatenate(output_values), np.concatenate(output_axis)
