from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from geoworkbench.calculations.curve_continuity import (
    CurveContinuityPolicy,
    estimate_short_gap_limit,
    interpolate_bounded_gaps as interpolate_bounded_gaps,
    interpolate_monotonic_unique,
)
from geoworkbench.domain.gas_conditioning_qc import (
    GasComponentConditioningQc,
    GasConditioningQcInterval,
    GasConditioningQcSummary,
)


Array = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
IntArray = NDArray[np.int64]


GasConditioningPolicy = CurveContinuityPolicy


@dataclass(frozen=True, slots=True)
class ConditionedGasComponents:
    """Conditioned components plus auditable interpolation provenance."""

    depth: Array
    components: dict[str, Array]
    interpolated_masks: dict[str, BoolArray]
    max_gap_by_component: dict[str, float | None]
    nominal_depth_step: float
    qc_summary: GasConditioningQcSummary

    def interpolated_count(self, mnemonic: str) -> int:
        return self.qc_summary.component(mnemonic).interpolated_sample_count


@dataclass(frozen=True, slots=True)
class _PreparedAxis:
    source: Array
    working: Array
    unique: Array
    inverse: IntArray
    nominal_step: float
    decreasing: bool


def _as_1d_float_array(values: Array, *, name: str) -> Array:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} должен быть одномерным массивом")
    return array


def _prepare_axis(depth: Array) -> _PreparedAxis:
    axis = _as_1d_float_array(depth, name="Глубина")
    if axis.size < 2:
        raise ValueError("Для кондиционирования нужны минимум две отметки глубины")
    if not np.all(np.isfinite(axis)):
        raise ValueError("Шкала глубины не должна содержать NaN или бесконечность")

    steps = np.diff(axis)
    increasing = bool(np.all(steps >= 0.0) and np.any(steps > 0.0))
    decreasing = bool(np.all(steps <= 0.0) and np.any(steps < 0.0))
    if not increasing and not decreasing:
        raise ValueError(
            "Шкала глубины должна быть монотонной; повторяющиеся отметки разрешены"
        )

    working = axis[::-1].copy() if decreasing else axis.copy()
    group_starts = np.concatenate(
        (
            np.array([0], dtype=np.int64),
            np.flatnonzero(working[1:] != working[:-1]).astype(np.int64) + 1,
        )
    )
    unique = working[group_starts]
    group_ends = np.concatenate(
        (group_starts[1:], np.array([working.size], dtype=np.int64))
    )
    group_counts = group_ends - group_starts
    inverse = np.repeat(
        np.arange(unique.size, dtype=np.int64),
        group_counts,
    )

    unique_steps = np.diff(unique)
    positive_steps = np.sort(unique_steps[unique_steps > 0.0])
    if positive_steps.size == 0:
        raise ValueError("Не удалось определить положительный шаг глубины")
    dense_half = positive_steps[: max(1, (positive_steps.size + 1) // 2)]
    nominal_step = float(np.median(dense_half))
    if not np.isfinite(nominal_step) or nominal_step <= 0.0:
        raise ValueError("Не удалось определить положительный шаг глубины")

    return _PreparedAxis(
        source=axis.copy(),
        working=working,
        unique=unique,
        inverse=inverse,
        nominal_step=nominal_step,
        decreasing=decreasing,
    )


def _collapse_values(values: Array, inverse: IntArray, unique_size: int) -> Array:
    finite = np.isfinite(values)
    collapsed = np.full(unique_size, np.nan, dtype=np.float64)
    if not np.any(finite):
        return collapsed

    sums = np.bincount(
        inverse[finite],
        weights=values[finite],
        minlength=unique_size,
    ).astype(np.float64, copy=False)
    counts = np.bincount(
        inverse[finite],
        minlength=unique_size,
    ).astype(np.int64, copy=False)
    np.divide(sums, counts, out=collapsed, where=counts > 0)
    return collapsed


def _expand_conditioned_values(
    source: Array,
    conditioned_unique: Array,
    inverse: IntArray,
) -> tuple[Array, BoolArray]:
    output = source.copy()
    output[~np.isfinite(output)] = np.nan
    replacement = conditioned_unique[inverse]
    fillable = ~np.isfinite(output) & np.isfinite(replacement)
    output[fillable] = replacement[fillable]
    return output, fillable.astype(np.bool_, copy=False)


def _mask_depth_intervals(
    depth: Array,
    mask: BoolArray,
) -> tuple[GasConditioningQcInterval, ...]:
    indices = np.flatnonzero(mask).astype(np.int64, copy=False)
    if indices.size == 0:
        return ()

    split_at = np.flatnonzero(np.diff(indices) > 1) + 1
    groups = np.split(indices, split_at)
    intervals: list[GasConditioningQcInterval] = []
    for group in groups:
        first_depth = float(depth[int(group[0])])
        last_depth = float(depth[int(group[-1])])
        intervals.append(
            GasConditioningQcInterval(
                minimum_depth=min(first_depth, last_depth),
                maximum_depth=max(first_depth, last_depth),
                sample_count=int(group.size),
            )
        )
    return tuple(intervals)


def _build_qc_summary(
    depth: Array,
    masks: Mapping[str, BoolArray],
    max_gap_by_component: Mapping[str, float | None],
    *,
    nominal_depth_step: float,
) -> GasConditioningQcSummary:
    components: list[GasComponentConditioningQc] = []
    affected_rows = np.zeros(depth.shape, dtype=np.bool_)
    interpolated_component_sample_count = 0

    for mnemonic in sorted(masks):
        mask = np.asarray(masks[mnemonic], dtype=np.bool_)
        count = int(np.count_nonzero(mask))
        interpolated_component_sample_count += count
        affected_rows |= mask
        components.append(
            GasComponentConditioningQc(
                mnemonic=mnemonic,
                interpolated_sample_count=count,
                interpolated_intervals=_mask_depth_intervals(depth, mask),
                max_gap=max_gap_by_component[mnemonic],
            )
        )

    return GasConditioningQcSummary(
        nominal_depth_step=nominal_depth_step,
        affected_depth_row_count=int(np.count_nonzero(affected_rows)),
        interpolated_component_sample_count=interpolated_component_sample_count,
        components=tuple(components),
    )


def condition_gas_components(
    depth: Array,
    components: Mapping[str, Array],
    *,
    policy: GasConditioningPolicy | None = None,
) -> ConditionedGasComponents:
    """Condition C1–C5 style channels on one immutable common depth basis.

    Complexity is O(N × C), where C is the small number of gas components.
    Axis grouping is prepared once and reused for all components. Source arrays
    are never mutated; case-insensitive duplicate mnemonics are rejected.
    """

    if not components:
        raise ValueError("Не переданы газовые компоненты")
    resolved_policy = policy or GasConditioningPolicy()
    prepared = _prepare_axis(depth)

    normalized: dict[str, Array] = {}
    for mnemonic, values in components.items():
        key = mnemonic.strip().upper()
        if not key:
            raise ValueError("Мнемоника газового компонента не должна быть пустой")
        if key in normalized:
            raise ValueError(f"Дублирующаяся мнемоника газового компонента: {key}")
        array = _as_1d_float_array(values, name=f"Компонент {key}")
        if array.shape != prepared.source.shape:
            raise ValueError(
                f"Компонент {key} имеет длину {array.size}, "
                f"ожидалась {prepared.source.size}"
            )
        copied = array.astype(np.float64, copy=True)
        copied[~np.isfinite(copied)] = np.nan
        normalized[key] = copied

    conditioned: dict[str, Array] = {}
    masks: dict[str, BoolArray] = {}
    limits: dict[str, float | None] = {}
    for mnemonic, source_values in normalized.items():
        working_values = source_values[::-1] if prepared.decreasing else source_values
        collapsed = _collapse_values(
            working_values,
            prepared.inverse,
            prepared.unique.size,
        )
        limit = estimate_short_gap_limit(
            prepared.unique,
            collapsed,
            nominal_step=prepared.nominal_step,
            policy=resolved_policy,
        )
        limits[mnemonic] = limit
        if limit is None:
            conditioned[mnemonic] = source_values.copy()
            masks[mnemonic] = np.zeros(source_values.shape, dtype=np.bool_)
            continue

        conditioned_unique = interpolate_monotonic_unique(
            prepared.unique,
            collapsed,
            max_gap=limit,
        )
        working_output, working_mask = _expand_conditioned_values(
            working_values,
            conditioned_unique,
            prepared.inverse,
        )
        if prepared.decreasing:
            conditioned[mnemonic] = working_output[::-1].copy()
            masks[mnemonic] = working_mask[::-1].copy()
        else:
            conditioned[mnemonic] = working_output
            masks[mnemonic] = working_mask

    qc_summary = _build_qc_summary(
        prepared.source,
        masks,
        limits,
        nominal_depth_step=prepared.nominal_step,
    )
    return ConditionedGasComponents(
        depth=prepared.source,
        components=conditioned,
        interpolated_masks=masks,
        max_gap_by_component=limits,
        nominal_depth_step=prepared.nominal_step,
        qc_summary=qc_summary,
    )
