from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class GasConditioningQcInterval:
    """One contiguous source-row interval restored by gas conditioning."""

    minimum_depth: float
    maximum_depth: float
    sample_count: int

    def __post_init__(self) -> None:
        if isinstance(self.minimum_depth, bool) or not isinstance(
            self.minimum_depth, (int, float)
        ):
            raise ValueError("minimum_depth должен быть числом")
        if isinstance(self.maximum_depth, bool) or not isinstance(
            self.maximum_depth, (int, float)
        ):
            raise ValueError("maximum_depth должен быть числом")
        if not isfinite(float(self.minimum_depth)) or not isfinite(float(self.maximum_depth)):
            raise ValueError("Границы QC-интервала должны быть конечными")
        if self.minimum_depth > self.maximum_depth:
            raise ValueError("minimum_depth не должен превышать maximum_depth")
        if (
            isinstance(self.sample_count, bool)
            or not isinstance(self.sample_count, int)
            or self.sample_count <= 0
        ):
            raise ValueError("sample_count должен быть положительным целым числом")


@dataclass(frozen=True, slots=True)
class GasComponentConditioningQc:
    """Structured QC provenance for one conditioned gas component."""

    mnemonic: str
    interpolated_sample_count: int
    interpolated_intervals: tuple[GasConditioningQcInterval, ...]
    max_gap: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.mnemonic, str):
            raise ValueError("Мнемоника газового компонента должна быть строкой")
        normalized = self.mnemonic.strip().upper()
        if not normalized:
            raise ValueError("Мнемоника газового компонента не должна быть пустой")
        if normalized != self.mnemonic:
            raise ValueError("Мнемоника QC должна быть нормализована в верхний регистр")
        if (
            isinstance(self.interpolated_sample_count, bool)
            or not isinstance(self.interpolated_sample_count, int)
            or self.interpolated_sample_count < 0
        ):
            raise ValueError("interpolated_sample_count должен быть неотрицательным целым")
        if not isinstance(self.interpolated_intervals, tuple) or not all(
            isinstance(item, GasConditioningQcInterval)
            for item in self.interpolated_intervals
        ):
            raise ValueError("interpolated_intervals должен содержать QC-интервалы")
        interval_count = sum(item.sample_count for item in self.interpolated_intervals)
        if interval_count != self.interpolated_sample_count:
            raise ValueError("Сумма QC-интервалов не совпадает со счётчиком восстановленных точек")
        if self.max_gap is not None:
            if isinstance(self.max_gap, bool) or not isinstance(self.max_gap, (int, float)):
                raise ValueError("max_gap должен быть числом или null")
            if not isfinite(float(self.max_gap)) or self.max_gap <= 0.0:
                raise ValueError("max_gap должен быть конечным положительным числом или null")


@dataclass(frozen=True, slots=True)
class GasConditioningQcSummary:
    """Deterministic conditioning provenance safe for project persistence and UI."""

    nominal_depth_step: float
    affected_depth_row_count: int
    interpolated_component_sample_count: int
    components: tuple[GasComponentConditioningQc, ...]

    def __post_init__(self) -> None:
        if isinstance(self.nominal_depth_step, bool) or not isinstance(
            self.nominal_depth_step, (int, float)
        ):
            raise ValueError("nominal_depth_step должен быть числом")
        if not isfinite(float(self.nominal_depth_step)) or self.nominal_depth_step <= 0.0:
            raise ValueError("nominal_depth_step должен быть конечным положительным числом")
        if (
            isinstance(self.affected_depth_row_count, bool)
            or not isinstance(self.affected_depth_row_count, int)
            or self.affected_depth_row_count < 0
        ):
            raise ValueError("affected_depth_row_count должен быть неотрицательным целым")
        if (
            isinstance(self.interpolated_component_sample_count, bool)
            or not isinstance(self.interpolated_component_sample_count, int)
            or self.interpolated_component_sample_count < 0
        ):
            raise ValueError(
                "interpolated_component_sample_count должен быть неотрицательным целым"
            )
        if not isinstance(self.components, tuple) or not all(
            isinstance(item, GasComponentConditioningQc) for item in self.components
        ):
            raise ValueError("components должен содержать QC-компоненты")
        expected = sum(item.interpolated_sample_count for item in self.components)
        if expected != self.interpolated_component_sample_count:
            raise ValueError("Суммарный QC-счётчик не совпадает со счётчиками компонентов")
        mnemonics = tuple(item.mnemonic for item in self.components)
        if mnemonics != tuple(sorted(mnemonics)) or len(set(mnemonics)) != len(mnemonics):
            raise ValueError("QC-компоненты должны быть уникальны и отсортированы по мнемонике")

    def component(self, mnemonic: str) -> GasComponentConditioningQc:
        key = mnemonic.strip().upper()
        for item in self.components:
            if item.mnemonic == key:
                return item
        raise KeyError(f"Газовый компонент не найден: {mnemonic}")
