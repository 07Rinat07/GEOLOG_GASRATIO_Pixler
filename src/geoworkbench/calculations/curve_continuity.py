from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class CurveContinuityPolicy:
    """One conservative continuity contract for calculations and rendering.

    Only bounded missing rows compatible with the normal source cadence may be
    interpolated. Long acquisition outages, leading/trailing holes and measured
    finite zero values remain explicit evidence in the conditioned arrays.
    """

    max_gap_steps: float = 4.0
    cadence_factor: float = 2.5
    minimum_finite_samples: int = 2
    absolute_max_gap: float | None = None

    def __post_init__(self) -> None:
        if not np.isfinite(self.max_gap_steps) or self.max_gap_steps <= 0.0:
            raise ValueError("max_gap_steps должен быть положительным конечным числом")
        if not np.isfinite(self.cadence_factor) or self.cadence_factor <= 0.0:
            raise ValueError("cadence_factor должен быть положительным конечным числом")
        if self.minimum_finite_samples < 2:
            raise ValueError("minimum_finite_samples должен быть не меньше 2")
        if self.absolute_max_gap is not None and (
            not np.isfinite(self.absolute_max_gap) or self.absolute_max_gap <= 0.0
        ):
            raise ValueError("absolute_max_gap должен быть положительным конечным числом")


def _as_1d_float(values: FloatArray, *, name: str) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} должен быть одномерным массивом")
    return array


def nominal_axis_step(axis: FloatArray) -> float | None:
    """Return the robust dense positive step of a monotonic engineering axis."""

    values = _as_1d_float(axis, name="Шкала")
    if values.size < 2:
        return None
    deltas = np.abs(np.diff(values))
    positive = np.sort(deltas[np.isfinite(deltas) & (deltas > 0.0)])
    if positive.size == 0:
        return None
    dense_half = positive[: max(1, (positive.size + 1) // 2)]
    step = float(np.median(dense_half))
    return step if np.isfinite(step) and step > 0.0 else None


def estimate_short_gap_limit(
    axis: FloatArray,
    values: FloatArray,
    *,
    nominal_step: float | None = None,
    policy: CurveContinuityPolicy | None = None,
) -> float | None:
    """Estimate the largest physical hole eligible for interpolation."""

    resolved = policy or CurveContinuityPolicy()
    axis_array = _as_1d_float(axis, name="Шкала")
    value_array = _as_1d_float(values, name="Кривая")
    if axis_array.shape != value_array.shape:
        raise ValueError("Шкала и значения кривой должны иметь одинаковую форму")

    finite_positions = np.flatnonzero(
        np.isfinite(axis_array) & np.isfinite(value_array)
    )
    if finite_positions.size < resolved.minimum_finite_samples:
        return None
    observed = np.abs(np.diff(axis_array[finite_positions]))
    observed = np.sort(observed[np.isfinite(observed) & (observed > 0.0)])
    if observed.size == 0:
        return None
    dense_half = observed[: max(1, (observed.size + 1) // 2)]
    normal_curve_step = float(np.median(dense_half))
    base_step = nominal_step if nominal_step is not None else nominal_axis_step(axis_array)
    candidates = [normal_curve_step * resolved.cadence_factor]
    if base_step is not None and np.isfinite(base_step) and base_step > 0.0:
        candidates.append(float(base_step) * resolved.max_gap_steps)
    limit = max(candidates)
    if resolved.absolute_max_gap is not None:
        limit = min(limit, resolved.absolute_max_gap)
    return limit if np.isfinite(limit) and limit > 0.0 else None


def interpolate_monotonic_unique(
    axis: FloatArray,
    values: FloatArray,
    *,
    max_gap: float,
) -> FloatArray:
    """Interpolate bounded missing rows on an increasing unique axis."""

    axis_array = _as_1d_float(axis, name="Шкала")
    output = _as_1d_float(values, name="Кривая").copy()
    if axis_array.shape != output.shape:
        raise ValueError("Шкала и значения кривой должны иметь одинаковую форму")
    if not np.isfinite(max_gap) or max_gap <= 0.0:
        raise ValueError("max_gap должен быть положительным конечным числом")
    if axis_array.size < 3:
        return output
    if not np.all(np.isfinite(axis_array)) or not np.all(np.diff(axis_array) > 0.0):
        raise ValueError("Шкала интерполяции должна строго возрастать")

    finite_positions = np.flatnonzero(np.isfinite(output))
    for left, right in zip(finite_positions[:-1], finite_positions[1:], strict=True):
        left_index = int(left)
        right_index = int(right)
        if right_index - left_index <= 1:
            continue
        distance = float(axis_array[right_index] - axis_array[left_index])
        if distance > max_gap:
            continue
        interior = slice(left_index + 1, right_index)
        missing = ~np.isfinite(output[interior])
        if not np.any(missing):
            continue
        interpolated = np.interp(
            axis_array[interior],
            (axis_array[left_index], axis_array[right_index]),
            (output[left_index], output[right_index]),
        )
        interior_values = output[interior]
        interior_values[missing] = interpolated[missing]
        output[interior] = interior_values
    return output


def interpolate_bounded_gaps(
    axis: FloatArray,
    values: FloatArray,
    *,
    max_gap: float,
) -> tuple[FloatArray, BoolArray]:
    """Interpolate bounded holes while preserving input order and evidence."""

    source_axis = _as_1d_float(axis, name="Глубина")
    source_values = _as_1d_float(values, name="Кривая")
    if source_axis.shape != source_values.shape:
        raise ValueError("Глубина и кривая должны иметь одинаковую длину")
    if source_axis.size < 2:
        raise ValueError("Для интерполяции нужны минимум две отметки глубины")
    if not np.all(np.isfinite(source_axis)):
        raise ValueError("Шкала глубины не должна содержать NaN или бесконечность")
    if not np.isfinite(max_gap) or max_gap <= 0.0:
        raise ValueError("max_gap должен быть положительным конечным числом")

    deltas = np.diff(source_axis)
    increasing = bool(np.all(deltas >= 0.0) and np.any(deltas > 0.0))
    decreasing = bool(np.all(deltas <= 0.0) and np.any(deltas < 0.0))
    if not increasing and not decreasing:
        raise ValueError(
            "Шкала глубины должна быть монотонной; повторяющиеся отметки разрешены"
        )

    working_axis = source_axis[::-1] if decreasing else source_axis
    working_values = source_values[::-1] if decreasing else source_values
    normalized = working_values.astype(np.float64, copy=True)
    normalized[~np.isfinite(normalized)] = np.nan

    unique_axis, inverse = np.unique(working_axis, return_inverse=True)
    finite = np.isfinite(normalized)
    collapsed = np.full(unique_axis.shape, np.nan, dtype=np.float64)
    if np.any(finite):
        sums = np.bincount(
            inverse[finite],
            weights=normalized[finite],
            minlength=unique_axis.size,
        ).astype(np.float64, copy=False)
        counts = np.bincount(
            inverse[finite],
            minlength=unique_axis.size,
        )
        np.divide(sums, counts, out=collapsed, where=counts > 0)

    conditioned_unique = interpolate_monotonic_unique(
        unique_axis,
        collapsed,
        max_gap=max_gap,
    )
    replacement = conditioned_unique[inverse]
    output = normalized.copy()
    mask = ~np.isfinite(output) & np.isfinite(replacement)
    output[mask] = replacement[mask]
    if decreasing:
        return output[::-1].copy(), mask[::-1].astype(np.bool_, copy=True)
    return output, mask.astype(np.bool_, copy=False)


def build_segment_connect_mask(axis: FloatArray, values: FloatArray) -> BoolArray:
    """Return PyQtGraph connectivity: mask[i] joins point i to point i+1.

    The final entry is always false because it has no following point. Explicit
    NaN separators produced before downsampling therefore remain hard segment
    boundaries, while every finite continuous segment is rendered as a line.
    """

    axis_array = _as_1d_float(axis, name="Шкала")
    value_array = _as_1d_float(values, name="Кривая")
    if axis_array.shape != value_array.shape:
        raise ValueError("Шкала и значения кривой должны иметь одинаковую форму")
    connect = np.zeros(axis_array.shape, dtype=np.bool_)
    if axis_array.size < 2:
        return connect
    finite = np.isfinite(axis_array) & np.isfinite(value_array)
    delta = np.diff(axis_array)
    connect[:-1] = (
        finite[:-1]
        & finite[1:]
        & np.isfinite(delta)
        & (delta != 0.0)
    )
    return connect
