from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


Array = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


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


def _as_1d_float_array(values: Array, *, name: str) -> Array:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} должен быть одномерным массивом")
    return array


def _validate_depth(depth: Array) -> tuple[Array, float]:
    axis = _as_1d_float_array(depth, name="Глубина")
    if axis.size < 2:
        raise ValueError("Для кондиционирования нужны минимум две отметки глубины")
    if not np.all(np.isfinite(axis)):
        raise ValueError("Шкала глубины не должна содержать NaN или бесконечность")

    steps = np.diff(axis)
    if not np.all(steps > 0.0):
        raise ValueError("Шкала глубины должна строго возрастать без дубликатов")

    ordered_steps = np.sort(steps)
    dense_half = ordered_steps[: max(1, (ordered_steps.size + 1) // 2)]
    nominal_step = float(np.median(dense_half))
    if not np.isfinite(nominal_step) or nominal_step <= 0.0:
        raise ValueError("Не удалось определить положительный шаг глубины")
    return axis.copy(), nominal_step


def _component_gap_limit(
    depth: Array,
    values: Array,
    *,
    nominal_depth_step: float,
    policy: GasConditioningPolicy,
) -> float | None:
    finite_positions = np.flatnonzero(np.isfinite(values))
    if finite_positions.size < policy.minimum_finite_samples:
        return None

    observed_steps = np.diff(depth[finite_positions])
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


def interpolate_bounded_gaps(
    depth: Array,
    values: Array,
    *,
    max_gap: float,
) -> tuple[Array, BoolArray]:
    """Interpolate short bounded ``NaN`` runs and return a provenance mask.

    Only rows between two finite measurements are eligible. Long acquisition
    outages, leading/trailing holes and explicit finite zero values are kept.
    """

    axis = _as_1d_float_array(depth, name="Глубина")
    source = _as_1d_float_array(values, name="Газовый компонент")
    if axis.shape != source.shape:
        raise ValueError("Глубина и газовый компонент должны иметь одинаковую длину")
    if not np.isfinite(max_gap) or max_gap <= 0.0:
        raise ValueError("max_gap должен быть положительным конечным числом")

    output = source.copy()
    output[~np.isfinite(output)] = np.nan
    interpolated = np.zeros(output.shape, dtype=np.bool_)
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
        interior_axis = axis[interior]
        interpolated_values = np.interp(
            interior_axis,
            (axis[left_index], axis[right_index]),
            (output[left_index], output[right_index]),
        )
        interior_values = output[interior]
        interior_values[missing] = interpolated_values[missing]
        output[interior] = interior_values
        mask_values = interpolated[interior]
        mask_values[missing] = True
        interpolated[interior] = mask_values

    return output, interpolated


def condition_gas_components(
    depth: Array,
    components: Mapping[str, Array],
    *,
    policy: GasConditioningPolicy | None = None,
) -> ConditionedGasComponents:
    """Condition C1–C5 style channels on one immutable common depth basis.

    Source arrays are never mutated. Mnemonics are normalized to upper case and
    case-insensitive duplicates are rejected to keep the result auditable.
    """

    if not components:
        raise ValueError("Не переданы газовые компоненты")
    resolved_policy = policy or GasConditioningPolicy()
    axis, nominal_depth_step = _validate_depth(depth)

    normalized: dict[str, Array] = {}
    for mnemonic, values in components.items():
        key = mnemonic.strip().upper()
        if not key:
            raise ValueError("Мнемоника газового компонента не должна быть пустой")
        if key in normalized:
            raise ValueError(f"Дублирующаяся мнемоника газового компонента: {key}")
        array = _as_1d_float_array(values, name=f"Компонент {key}")
        if array.shape != axis.shape:
            raise ValueError(
                f"Компонент {key} имеет длину {array.size}, ожидалась {axis.size}"
            )
        copied = array.copy()
        copied[~np.isfinite(copied)] = np.nan
        normalized[key] = copied

    conditioned: dict[str, Array] = {}
    masks: dict[str, BoolArray] = {}
    limits: dict[str, float | None] = {}
    for mnemonic, values in normalized.items():
        limit = _component_gap_limit(
            axis,
            values,
            nominal_depth_step=nominal_depth_step,
            policy=resolved_policy,
        )
        limits[mnemonic] = limit
        if limit is None:
            conditioned[mnemonic] = values.copy()
            masks[mnemonic] = np.zeros(values.shape, dtype=np.bool_)
            continue
        conditioned_values, interpolation_mask = interpolate_bounded_gaps(
            axis,
            values,
            max_gap=limit,
        )
        conditioned[mnemonic] = conditioned_values
        masks[mnemonic] = interpolation_mask

    return ConditionedGasComponents(
        depth=axis,
        components=conditioned,
        interpolated_masks=masks,
        max_gap_by_component=limits,
        nominal_depth_step=nominal_depth_step,
    )
