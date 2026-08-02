from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


Array = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class GasConditioningPolicy:
    """Conservative policy for conditioning sparse gas measurements.

    The policy fills only bounded holes whose physical depth span is compatible
    with the normal acquisition cadence. Long outages remain explicit ``NaN``
    gaps and measured zero values are never overwritten.
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


@dataclass(frozen=True, slots=True)
class ConditionedGasComponents:
    """Conditioned components plus auditable interpolation provenance."""

    depth: Array
    components: dict[str, Array]
    interpolated_masks: dict[str, BoolArray]
    max_gap_by_component: dict[str, float | None]
    nominal_depth_step: float

    def interpolated_count(self, mnemonic: str) -> int:
        key = mnemonic.strip().upper()
        try:
            return int(np.count_nonzero(self.interpolated_masks[key]))
        except KeyError as exc:
            raise KeyError(f"Газовый компонент не найден: {mnemonic}") from exc


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


def _component_gap_limit(
    unique_depth: Array,
    collapsed_values: Array,
    *,
    nominal_depth_step: float,
    policy: GasConditioningPolicy,
) -> float | None:
    finite_positions = np.flatnonzero(np.isfinite(collapsed_values))
    if finite_positions.size < policy.minimum_finite_samples:
        return None

    observed_steps = np.diff(unique_depth[finite_positions])
    observed_steps = observed_steps[
        np.isfinite(observed_steps) & (observed_steps > 0.0)
    ]
    if observed_steps.size == 0:
        return None

    ordered_steps = np.sort(observed_steps)
    dense_half = ordered_steps[: max(1, (ordered_steps.size + 1) // 2)]
    normal_component_step = float(np.median(dense_half))
    limit = max(
        nominal_depth_step * policy.max_gap_steps,
        normal_component_step * policy.cadence_factor,
    )
    if policy.absolute_max_gap is not None:
        limit = min(limit, policy.absolute_max_gap)
    return limit if np.isfinite(limit) and limit > 0.0 else None


def _interpolate_unique_axis(
    axis: Array,
    source: Array,
    *,
    max_gap: float,
) -> Array:
    output = source.copy()
    finite_positions = np.flatnonzero(np.isfinite(output))

    for left, right in zip(finite_positions[:-1], finite_positions[1:], strict=True):
        left_index = int(left)
        right_index = int(right)
        if right_index - left_index <= 1:
            continue
        distance = float(axis[right_index] - axis[left_index])
        if not np.isfinite(distance) or distance <= 0.0 or distance > max_gap:
            continue

        interior = slice(left_index + 1, right_index)
        missing = ~np.isfinite(output[interior])
        if not np.any(missing):
            continue
        interpolated_values = np.interp(
            axis[interior],
            (axis[left_index], axis[right_index]),
            (output[left_index], output[right_index]),
        )
        interior_values = output[interior]
        interior_values[missing] = interpolated_values[missing]
        output[interior] = interior_values

    return output


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


def interpolate_bounded_gaps(
    depth: Array,
    values: Array,
    *,
    max_gap: float,
) -> tuple[Array, BoolArray]:
    """Interpolate short bounded ``NaN`` runs and return a provenance mask.

    Increasing/decreasing axes and repeated depth rows are supported. Finite
    source measurements are never overwritten. Only missing rows between two
    finite measurements are eligible; long outages and edge holes remain gaps.
    """

    prepared = _prepare_axis(depth)
    source = _as_1d_float_array(values, name="Газовый компонент")
    if prepared.source.shape != source.shape:
        raise ValueError("Глубина и газовый компонент должны иметь одинаковую длину")
    if not np.isfinite(max_gap) or max_gap <= 0.0:
        raise ValueError("max_gap должен быть положительным конечным числом")

    working_source = source[::-1] if prepared.decreasing else source
    normalized_source = working_source.astype(np.float64, copy=True)
    normalized_source[~np.isfinite(normalized_source)] = np.nan
    collapsed = _collapse_values(
        normalized_source,
        prepared.inverse,
        prepared.unique.size,
    )
    conditioned_unique = _interpolate_unique_axis(
        prepared.unique,
        collapsed,
        max_gap=max_gap,
    )
    output, interpolated = _expand_conditioned_values(
        normalized_source,
        conditioned_unique,
        prepared.inverse,
    )
    if prepared.decreasing:
        return output[::-1].copy(), interpolated[::-1].copy()
    return output, interpolated


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
        working_values = (
            source_values[::-1]
            if prepared.decreasing
            else source_values
        )
        collapsed = _collapse_values(
            working_values,
            prepared.inverse,
            prepared.unique.size,
        )
        limit = _component_gap_limit(
            prepared.unique,
            collapsed,
            nominal_depth_step=prepared.nominal_step,
            policy=resolved_policy,
        )
        limits[mnemonic] = limit
        if limit is None:
            conditioned[mnemonic] = source_values.copy()
            masks[mnemonic] = np.zeros(source_values.shape, dtype=np.bool_)
            continue

        conditioned_unique = _interpolate_unique_axis(
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

    return ConditionedGasComponents(
        depth=prepared.source,
        components=conditioned,
        interpolated_masks=masks,
        max_gap_by_component=limits,
        nominal_depth_step=prepared.nominal_step,
    )
