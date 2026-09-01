from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GasConditioningQcInterval:
    """One contiguous source-row interval restored by gas conditioning."""

    minimum_depth: float
    maximum_depth: float
    sample_count: int

    def __post_init__(self) -> None:
        if self.minimum_depth > self.maximum_depth:
            raise ValueError("minimum_depth не должен превышать maximum_depth")
        if isinstance(self.sample_count, bool) or self.sample_count <= 0:
            raise ValueError("sample_count должен быть положительным целым числом")


@dataclass(frozen=True, slots=True)
class GasComponentConditioningQc:
    """Structured QC provenance for one conditioned gas component."""

    mnemonic: str
    interpolated_sample_count: int
    interpolated_intervals: tuple[GasConditioningQcInterval, ...]
    max_gap: float | None

    def __post_init__(self) -> None:
        normalized = self.mnemonic.strip().upper()
        if not normalized:
            raise ValueError("Мнемоника газового компонента не должна быть пустой")
        if normalized != self.mnemonic:
            raise ValueError("Мнемоника QC должна быть нормализована в верхний регистр")
        if isinstance(self.interpolated_sample_count, bool) or self.interpolated_sample_count < 0:
            raise ValueError("interpolated_sample_count должен быть неотрицательным целым")
        interval_count = sum(item.sample_count for item in self.interpolated_intervals)
        if interval_count != self.interpolated_sample_count:
            raise ValueError("Сумма QC-интервалов не совпадает со счётчиком восстановленных точек")
        if self.max_gap is not None and self.max_gap <= 0.0:
            raise ValueError("max_gap должен быть положительным или null")


@dataclass(frozen=True, slots=True)
class GasConditioningQcSummary:
    """Deterministic conditioning provenance safe for project persistence and UI."""

    nominal_depth_step: float
    affected_depth_row_count: int
    interpolated_component_sample_count: int
    components: tuple[GasComponentConditioningQc, ...]

    def __post_init__(self) -> None:
        if self.nominal_depth_step <= 0.0:
            raise ValueError("nominal_depth_step должен быть положительным")
        if isinstance(self.affected_depth_row_count, bool) or self.affected_depth_row_count < 0:
            raise ValueError("affected_depth_row_count должен быть неотрицательным целым")
        if (
            isinstance(self.interpolated_component_sample_count, bool)
            or self.interpolated_component_sample_count < 0
        ):
            raise ValueError(
                "interpolated_component_sample_count должен быть неотрицательным целым"
            )
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
