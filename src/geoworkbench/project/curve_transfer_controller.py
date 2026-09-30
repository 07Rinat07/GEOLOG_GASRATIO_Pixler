from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.edit_history import CommandHistory
from geoworkbench.services.curve_transfer import (
    CurveTransferAnalysis,
    analyze_curve_transfer,
    build_transferred_curves,
)


@dataclass(slots=True)
class _CurveTransferCommand:
    target_dataset_id: str
    curves: tuple[CurveData, ...]
    initial_metadata: tuple[CurveMetadata, ...]
    initial_values: tuple[NDArray[np.float64], ...]


@dataclass(slots=True)
class _CurveTransferHistoryCommand:
    controller: "CurveTransferController" = field(repr=False)
    transfer: _CurveTransferCommand = field(repr=False)
    description: str = "Перенос кривых"
    history_domain: str = field(default="curve_transfer", init=False, repr=False)

    def execute(self) -> None:
        self.controller._redo_command(self.transfer)

    def undo(self) -> None:
        self.controller._undo_command(self.transfer)


@dataclass(slots=True)
class CurveTransferController:
    session: ProjectSession
    max_commands: int = 100
    shared_history: CommandHistory | None = field(default=None, kw_only=True, repr=False)
    _history: CommandHistory = field(init=False, repr=False)

    _HISTORY_DOMAIN = "curve_transfer"

    def __post_init__(self) -> None:
        if self.max_commands < 1:
            raise ValueError("История должна хранить минимум одну команду")
        self._history = self.shared_history or CommandHistory(max_commands=self.max_commands)

    @property
    def can_undo(self) -> bool:
        command = self._history.next_undo
        return (
            isinstance(command, _CurveTransferHistoryCommand)
            and command.history_domain == self._HISTORY_DOMAIN
        )

    @property
    def can_redo(self) -> bool:
        command = self._history.next_redo
        return (
            isinstance(command, _CurveTransferHistoryCommand)
            and command.history_domain == self._HISTORY_DOMAIN
        )

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
        transfer = _CurveTransferCommand(
            target.dataset_id,
            curves,
            tuple(deepcopy(curve.metadata) for curve in curves),
            tuple(curve.values.copy() for curve in curves),
        )
        self._history.record_applied(_CurveTransferHistoryCommand(self, transfer))
        self.session.dirty = True
        return curves

    def undo(self) -> tuple[CurveData, ...]:
        command = self._require_history_command(redo=False)
        self._history.undo()
        return command.transfer.curves

    def redo(self) -> tuple[CurveData, ...]:
        command = self._require_history_command(redo=True)
        self._history.redo()
        return command.transfer.curves

    def clear_history(self) -> None:
        self._history.clear()

    def _undo_command(self, command: _CurveTransferCommand) -> None:
        target = self._require_command_target(command)
        for curve, initial_metadata, initial_values in zip(
            command.curves,
            command.initial_metadata,
            command.initial_values,
            strict=True,
        ):
            if target.curves.get(curve.metadata.curve_id) is not curve:
                raise RuntimeError("Вставленная кривая была изменена вне истории команд")
            if curve.metadata != initial_metadata or not np.array_equal(
                curve.values, initial_values, equal_nan=True
            ):
                raise RuntimeError(
                    "Вставленная кривая содержит последующие правки; Undo заблокирован"
                )
        for curve in command.curves:
            del target.curves[curve.metadata.curve_id]
        self.session.dirty = True

    def _redo_command(self, command: _CurveTransferCommand) -> None:
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
        self.session.dirty = True

    def _require_history_command(self, *, redo: bool) -> _CurveTransferHistoryCommand:
        command = self._history.next_redo if redo else self._history.next_undo
        if (
            not isinstance(command, _CurveTransferHistoryCommand)
            or command.history_domain != self._HISTORY_DOMAIN
        ):
            operation = "повтора" if redo else "отмены"
            raise RuntimeError(f"Нет вставки кривых для {operation}")
        return command

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
