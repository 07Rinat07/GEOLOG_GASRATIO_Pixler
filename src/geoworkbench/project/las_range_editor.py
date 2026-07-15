from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.edit_history import CurveEditCommand
from geoworkbench.services.dataset_selection import depth_interval_indices


@dataclass(frozen=True, slots=True)
class RangeClipboard:
    source_depth: NDArray[np.float64]
    values_by_curve_id: dict[str, NDArray[np.float64]]


@dataclass(slots=True)
class _RangeCommand:
    commands: tuple[CurveEditCommand, ...]
    description: str

    def execute(self) -> None:
        applied: list[CurveEditCommand] = []
        try:
            for command in self.commands:
                command.execute()
                applied.append(command)
        except Exception:
            for command in reversed(applied):
                command.undo()
            raise

    def undo(self) -> None:
        undone: list[CurveEditCommand] = []
        try:
            for command in reversed(self.commands):
                command.undo()
                undone.append(command)
        except Exception:
            for command in reversed(undone):
                command.execute()
            raise


@dataclass(slots=True)
class LasRangeEditingController:
    session: ProjectSession
    max_commands: int = 100
    _undo_stack: list[_RangeCommand] = field(default_factory=list, init=False)
    _redo_stack: list[_RangeCommand] = field(default_factory=list, init=False)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def set_constant(
        self,
        curve_ids: list[str],
        depth_top: float,
        depth_bottom: float,
        value: float,
    ) -> None:
        if not np.isfinite(value):
            raise ValueError("Значение должно быть конечным")
        indices = self._selected_indices(depth_top, depth_bottom)
        values = {
            curve_id: np.full(indices.size, value, dtype=np.float64)
            for curve_id in curve_ids
        }
        self._execute(curve_ids, indices, values, "Заполнение постоянным значением")

    def fill_uniform_noise(
        self,
        curve_ids: list[str],
        depth_top: float,
        depth_bottom: float,
        minimum: float,
        maximum: float,
        *,
        seed: int,
    ) -> None:
        if not np.isfinite(minimum) or not np.isfinite(maximum) or minimum > maximum:
            raise ValueError("Некорректный диапазон случайных значений")
        indices = self._selected_indices(depth_top, depth_bottom)
        generator = np.random.default_rng(seed)
        values = {
            curve_id: generator.uniform(minimum, maximum, indices.size)
            for curve_id in curve_ids
        }
        self._execute(
            curve_ids,
            indices,
            values,
            f"Случайные значения {minimum:g}–{maximum:g}; seed={seed}",
        )

    def copy(
        self, curve_ids: list[str], depth_top: float, depth_bottom: float
    ) -> RangeClipboard:
        dataset = self._require_dataset()
        indices = self._selected_indices(depth_top, depth_bottom)
        curves = self._require_curves(dataset, curve_ids)
        return RangeClipboard(
            source_depth=np.asarray(dataset.depth[indices], dtype=np.float64).copy(),
            values_by_curve_id={
                curve.metadata.curve_id: np.asarray(curve.values[indices], dtype=np.float64).copy()
                for curve in curves
            },
        )

    def paste(self, clipboard: RangeClipboard, target_start_depth: float) -> None:
        dataset = self._require_dataset()
        if clipboard.source_depth.size == 0:
            raise ValueError("Буфер диапазона пуст")
        finite_depth = np.isfinite(dataset.depth)
        if not np.any(finite_depth):
            raise ValueError("В dataset нет конечной глубины")
        candidate_indices = np.flatnonzero(finite_depth)
        nearest_offset = int(
            np.argmin(np.abs(dataset.depth[candidate_indices] - target_start_depth))
        )
        start_index = int(candidate_indices[nearest_offset])
        stop_index = start_index + clipboard.source_depth.size
        if stop_index > dataset.depth.size:
            raise ValueError("Вставляемый диапазон выходит за границы dataset")
        indices = np.arange(start_index, stop_index, dtype=np.int64)
        curve_ids = list(clipboard.values_by_curve_id)
        self._execute(
            curve_ids,
            indices,
            clipboard.values_by_curve_id,
            f"Вставка диапазона с глубины {target_start_depth:g}",
        )

    def undo(self) -> None:
        if not self._undo_stack:
            raise RuntimeError("Нет диапазонных команд для отмены")
        command = self._undo_stack[-1]
        command.undo()
        self._undo_stack.pop()
        self._redo_stack.append(command)
        self._after_change()

    def redo(self) -> None:
        if not self._redo_stack:
            raise RuntimeError("Нет диапазонных команд для повтора")
        command = self._redo_stack[-1]
        command.execute()
        self._redo_stack.pop()
        self._undo_stack.append(command)
        self._after_change()

    def _execute(
        self,
        curve_ids: list[str],
        indices: NDArray[np.int64],
        values_by_curve_id: dict[str, NDArray[np.float64]],
        description: str,
    ) -> None:
        dataset = self._require_dataset()
        curves = self._require_curves(dataset, curve_ids)
        commands = tuple(
            CurveEditCommand.create(
                curve,
                indices,
                np.asarray(values_by_curve_id[curve.metadata.curve_id], dtype=np.float64),
                description=description,
            )
            for curve in curves
        )
        command = _RangeCommand(commands, description)
        command.execute()
        self._undo_stack.append(command)
        if len(self._undo_stack) > self.max_commands:
            del self._undo_stack[0]
        self._redo_stack.clear()
        self._after_change()

    def _after_change(self) -> None:
        try:
            self.session.calculate_basic_gas_ratios()
        except KeyError:
            self.session.dirty = True

    def _selected_indices(self, depth_top: float, depth_bottom: float) -> NDArray[np.int64]:
        return depth_interval_indices(self._require_dataset(), depth_top, depth_bottom)

    @staticmethod
    def _require_curves(dataset: Dataset, curve_ids: list[str]) -> list[CurveData]:
        if not curve_ids:
            raise ValueError("Выберите хотя бы одну кривую")
        missing = [curve_id for curve_id in curve_ids if curve_id not in dataset.curves]
        if missing:
            raise KeyError(f"Кривые не найдены: {', '.join(missing)}")
        curves = [dataset.curves[curve_id] for curve_id in curve_ids]
        calculated = [
            curve.metadata.original_mnemonic
            for curve in curves
            if curve.metadata.provenance.startswith("calculation:")
        ]
        if calculated:
            raise ValueError(
                "Расчётные кривые редактируются через исходные параметры: "
                + ", ".join(calculated)
            )
        return curves

    def _require_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите dataset")
        return dataset
