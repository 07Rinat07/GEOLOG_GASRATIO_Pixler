from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.las_parameter_resolver import ParameterResolutionError
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
            curve_id: np.full(indices.size, value, dtype=np.float64) for curve_id in curve_ids
        }
        self._execute(curve_ids, indices, values, "Заполнение постоянным значением")

    def set_missing(self, curve_ids: list[str], depth_top: float, depth_bottom: float) -> None:
        indices = self._selected_indices(depth_top, depth_bottom)
        values = {
            curve_id: np.full(indices.size, np.nan, dtype=np.float64) for curve_id in curve_ids
        }
        self._execute(curve_ids, indices, values, "Замена значений пропусками")

    def add_constant(
        self,
        curve_ids: list[str],
        depth_top: float,
        depth_bottom: float,
        offset: float,
    ) -> None:
        if not np.isfinite(offset):
            raise ValueError("Смещение должно быть конечным")
        dataset = self._require_dataset()
        indices = self._selected_indices(depth_top, depth_bottom)
        curves = self._require_curves(dataset, curve_ids)
        values = {
            curve.metadata.curve_id: np.asarray(curve.values[indices] + offset, dtype=np.float64)
            for curve in curves
        }
        self._execute(curve_ids, indices, values, f"Сдвиг значений на {offset:g}")

    def multiply(
        self,
        curve_ids: list[str],
        depth_top: float,
        depth_bottom: float,
        factor: float,
    ) -> None:
        if not np.isfinite(factor):
            raise ValueError("Множитель должен быть конечным")
        dataset = self._require_dataset()
        indices = self._selected_indices(depth_top, depth_bottom)
        curves = self._require_curves(dataset, curve_ids)
        values = {
            curve.metadata.curve_id: np.asarray(curve.values[indices] * factor, dtype=np.float64)
            for curve in curves
        }
        self._execute(curve_ids, indices, values, f"Умножение значений на {factor:g}")

    def smooth_moving_average(
        self,
        curve_ids: list[str],
        depth_top: float,
        depth_bottom: float,
        window: int,
    ) -> None:
        if isinstance(window, bool) or not isinstance(window, (int, np.integer)):
            raise ValueError("Размер окна должен быть целым числом")
        if window < 3 or window % 2 == 0:
            raise ValueError("Размер окна должен быть нечётным числом не меньше 3")
        dataset = self._require_dataset()
        indices = self._selected_indices(depth_top, depth_bottom)
        if window > indices.size:
            raise ValueError("Размер окна превышает выбранный интервал")
        curves = self._require_curves(dataset, curve_ids)
        kernel = np.ones(window, dtype=np.float64)
        values: dict[str, NDArray[np.float64]] = {}
        for curve in curves:
            selected = np.asarray(curve.values[indices], dtype=np.float64)
            finite = np.isfinite(selected)
            totals = np.convolve(np.where(finite, selected, 0.0), kernel, mode="same")
            counts = np.convolve(finite.astype(np.float64), kernel, mode="same")
            smoothed = np.full(selected.shape, np.nan, dtype=np.float64)
            writable = finite & (counts > 0)
            smoothed[writable] = totals[writable] / counts[writable]
            values[curve.metadata.curve_id] = smoothed
        self._execute(
            curve_ids,
            indices,
            values,
            f"Скользящее среднее, окно {window}",
        )

    def interpolate_missing(
        self, curve_ids: list[str], depth_top: float, depth_bottom: float
    ) -> None:
        dataset = self._require_dataset()
        selected_indices = self._selected_indices(depth_top, depth_bottom)
        curves = self._require_curves(dataset, curve_ids)
        changes: dict[str, tuple[NDArray[np.int64], NDArray[np.float64]]] = {}

        for curve in curves:
            targets = selected_indices[
                np.isnan(curve.values[selected_indices])
                & np.isfinite(dataset.depth[selected_indices])
            ]
            if targets.size == 0:
                continue
            anchors = np.flatnonzero(np.isfinite(dataset.depth) & np.isfinite(curve.values)).astype(
                np.int64
            )
            if anchors.size < 2:
                continue
            order = np.argsort(dataset.depth[anchors], kind="stable")
            anchor_depth = dataset.depth[anchors[order]]
            if np.any(np.diff(anchor_depth) <= 0):
                raise ValueError("Линейная интерполяция требует уникального монотонного индекса")
            bounded = targets[
                (dataset.depth[targets] >= anchor_depth[0])
                & (dataset.depth[targets] <= anchor_depth[-1])
            ]
            if bounded.size == 0:
                continue
            changes[curve.metadata.curve_id] = (
                bounded,
                np.interp(
                    dataset.depth[bounded],
                    anchor_depth,
                    curve.values[anchors[order]],
                ),
            )

        if not changes:
            raise ValueError("В выбранном интервале нет ограниченных с двух сторон пропусков")
        self._execute_changes(changes, "Линейная интерполяция пропусков")

    def edit_cell(self, curve_id: str, row: int, value: float) -> None:
        dataset = self._require_dataset()
        if row < 0 or row >= dataset.depth.size:
            raise IndexError("Строка выходит за границы dataset")
        if not np.isfinite(value):
            raise ValueError("Значение должно быть конечным")
        self._execute(
            [curve_id],
            np.array([row], dtype=np.int64),
            {curve_id: np.array([value], dtype=np.float64)},
            f"Табличное редактирование строки {row + 1}",
        )

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
            curve_id: generator.uniform(minimum, maximum, indices.size) for curve_id in curve_ids
        }
        self._execute(
            curve_ids,
            indices,
            values,
            f"Случайные значения {minimum:g}–{maximum:g}; seed={seed}",
        )

    def copy(self, curve_ids: list[str], depth_top: float, depth_bottom: float) -> RangeClipboard:
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
        self._execute_changes(
            {curve_id: (indices, values_by_curve_id[curve_id]) for curve_id in curve_ids},
            description,
        )

    def _execute_changes(
        self,
        changes: dict[str, tuple[NDArray[np.int64], NDArray[np.float64]]],
        description: str,
    ) -> None:
        dataset = self._require_dataset()
        curve_ids = list(changes)
        curves = self._require_curves(dataset, curve_ids)
        commands = tuple(
            CurveEditCommand.create(
                curve,
                np.asarray(changes[curve.metadata.curve_id][0], dtype=np.int64),
                np.asarray(changes[curve.metadata.curve_id][1], dtype=np.float64),
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
        except (KeyError, ParameterResolutionError):
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
                "Расчётные кривые редактируются через исходные параметры: " + ", ".join(calculated)
            )
        return curves

    def _require_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите dataset")
        return dataset
