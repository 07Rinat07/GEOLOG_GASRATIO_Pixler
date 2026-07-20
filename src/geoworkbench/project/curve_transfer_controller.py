from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.curve_transfer import (
    CurveTransferAnalysis,
    analyze_curve_transfer,
    build_transferred_curves,
)


@dataclass(slots=True)
class _CurveTransferCommand:
    target_dataset_id: str
    curves: tuple[CurveData, ...]
    initial_values: tuple[NDArray[np.float64], ...]


@dataclass(slots=True)
class CurveTransferController:
    session: ProjectSession
    _undo_stack: list[_CurveTransferCommand] = field(default_factory=list, init=False)
    _redo_stack: list[_CurveTransferCommand] = field(default_factory=list, init=False)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def analyze(self, source_dataset_id: str) -> CurveTransferAnalysis:
        return analyze_curve_transfer(self._dataset(source_dataset_id), self._target_dataset())

    def available_sources(self) -> tuple[Dataset, ...]:
        target = self._target_dataset()
        return tuple(
            dataset
            for well in self.session.project.wells.values()
            for dataset in well.datasets.values()
            if dataset.dataset_id != target.dataset_id
        )

    def apply(
        self,
        source_dataset_id: str,
        curve_ids: tuple[str, ...],
        analysis: CurveTransferAnalysis,
    ) -> tuple[CurveData, ...]:
        target = self._target_dataset()
        curves = build_transferred_curves(
            self._dataset(source_dataset_id),
            target,
            curve_ids,
            analysis=analysis,
        )
        for curve in curves:
            target.curves[curve.metadata.curve_id] = curve
        self._undo_stack.append(
            _CurveTransferCommand(
                target.dataset_id,
                curves,
                tuple(curve.values.copy() for curve in curves),
            )
        )
        self._redo_stack.clear()
        self.session.dirty = True
        return curves

    def undo(self) -> None:
        if not self._undo_stack:
            raise RuntimeError("Нет вставки кривых для отмены")
        command = self._undo_stack[-1]
        target = self._require_command_target(command)
        for curve, initial_values in zip(command.curves, command.initial_values, strict=True):
            if target.curves.get(curve.metadata.curve_id) is not curve:
                raise RuntimeError("Вставленная кривая была изменена вне истории команд")
            if curve.version != 1 or not np.array_equal(
                curve.values, initial_values, equal_nan=True
            ):
                raise RuntimeError(
                    "Вставленная кривая содержит последующие правки; Undo заблокирован"
                )
        for curve in command.curves:
            del target.curves[curve.metadata.curve_id]
        self._undo_stack.pop()
        self._redo_stack.append(command)
        self.session.dirty = True

    def redo(self) -> None:
        if not self._redo_stack:
            raise RuntimeError("Нет вставки кривых для повтора")
        command = self._redo_stack[-1]
        target = self._require_command_target(command)
        occupied = [
            curve.metadata.curve_id
            for curve in command.curves
            if curve.metadata.curve_id in target.curves
        ]
        if occupied:
            raise RuntimeError("Идентификаторы вставленных кривых уже заняты")
        for curve in command.curves:
            target.curves[curve.metadata.curve_id] = curve
        self._redo_stack.pop()
        self._undo_stack.append(command)
        self.session.dirty = True

    def clear_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    def _require_command_target(self, command: _CurveTransferCommand) -> Dataset:
        target = self._target_dataset()
        if target.dataset_id != command.target_dataset_id:
            raise RuntimeError("История вставки относится к другому dataset")
        return target

    def _target_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите dataset-приёмник")
        return dataset

    def _dataset(self, dataset_id: str) -> Dataset:
        for well in self.session.project.wells.values():
            if dataset_id in well.datasets:
                return well.datasets[dataset_id]
        raise KeyError(f"Dataset-источник не найден: {dataset_id}")
