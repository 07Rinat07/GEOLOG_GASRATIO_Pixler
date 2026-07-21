from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from geoworkbench.data.las_adapter import import_las_with_report
from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.dependent_recalculation import (
    DependentRecalculationReport,
    recalculate_existing_dependents,
)
from geoworkbench.services.external_las_insert import (
    ExternalLasCurveSelection,
    ExternalLasInsertAnalysis,
    analyze_external_las_insert,
    build_external_las_curves,
)
if TYPE_CHECKING:
    from geoworkbench.calculations.pixler import FormulaProfileRegistry


@dataclass(slots=True)
class _ExternalLasInsertCommand:
    target_dataset_id: str
    source_path: Path
    curves: tuple[CurveData, ...]
    initial_values: tuple[np.ndarray, ...]
    manifest_key: str
    previous_manifest: str | None
    manifest_json: str
    applied: bool = True


@dataclass(frozen=True, slots=True)
class ExternalLasInsertOutcome:
    inserted_mnemonics: tuple[str, ...]
    recalculation: DependentRecalculationReport


@dataclass(slots=True)
class ExternalLasInsertController:
    session: ProjectSession
    formula_registry: "FormulaProfileRegistry | None" = None
    _analysis: ExternalLasInsertAnalysis | None = field(default=None, init=False)
    _source_dataset: Dataset | None = field(default=None, init=False)
    _command: _ExternalLasInsertCommand | None = field(default=None, init=False)

    @property
    def can_undo(self) -> bool:
        command = self._command
        target = self.session.current_dataset
        return bool(
            command is not None
            and command.applied
            and target is not None
            and target.dataset_id == command.target_dataset_id
        )

    @property
    def can_redo(self) -> bool:
        command = self._command
        target = self.session.current_dataset
        return bool(
            command is not None
            and not command.applied
            and target is not None
            and target.dataset_id == command.target_dataset_id
        )

    def analyze_file(self, path: str | Path) -> ExternalLasInsertAnalysis:
        imported = import_las_with_report(path)
        target = self._target()
        analysis, source = analyze_external_las_insert(imported, target)
        self._analysis = analysis
        self._source_dataset = source
        return analysis

    def apply(
        self,
        analysis: ExternalLasInsertAnalysis,
        selections: tuple[ExternalLasCurveSelection, ...],
    ) -> ExternalLasInsertOutcome:
        target = self._target()
        if self._analysis != analysis or self._source_dataset is None:
            raise ValueError("Сначала повторно проанализируйте внешний LAS")
        build = build_external_las_curves(self._source_dataset, target, analysis, selections)
        for curve in build.curves:
            target.curves[curve.metadata.curve_id] = curve
        manifest_key = _next_manifest_key(target)
        previous = target.parameters.get(manifest_key)
        target.parameters[manifest_key] = build.manifest_json
        self._command = _ExternalLasInsertCommand(
            target_dataset_id=target.dataset_id,
            source_path=analysis.source_path,
            curves=build.curves,
            initial_values=tuple(curve.values.copy() for curve in build.curves),
            manifest_key=manifest_key,
            previous_manifest=previous,
            manifest_json=build.manifest_json,
        )
        recalculation = recalculate_existing_dependents(
            self.session,
            target,
            formula_registry=self.formula_registry,
        )
        self.session.dirty = True
        return ExternalLasInsertOutcome(
            tuple(curve.metadata.original_mnemonic for curve in build.curves),
            recalculation,
        )

    def undo(self) -> ExternalLasInsertOutcome:
        command = self._require_command(applied=True)
        target = self._target()
        for curve, original_values in zip(command.curves, command.initial_values, strict=True):
            current = target.curves.get(curve.metadata.curve_id)
            if current is not curve:
                raise RuntimeError("Вставленная кривая была удалена или заменена вне истории")
            if curve.version != 1 or not np.array_equal(
                curve.values, original_values, equal_nan=True
            ):
                raise RuntimeError(
                    "Вставленные кривые содержат последующие правки; Undo заблокирован"
                )
        for curve in command.curves:
            del target.curves[curve.metadata.curve_id]
        if command.previous_manifest is None:
            target.parameters.pop(command.manifest_key, None)
        else:
            target.parameters[command.manifest_key] = command.previous_manifest
        command.applied = False
        recalculation = recalculate_existing_dependents(
            self.session,
            target,
            formula_registry=self.formula_registry,
        )
        self.session.dirty = True
        return ExternalLasInsertOutcome(
            tuple(curve.metadata.original_mnemonic for curve in command.curves),
            recalculation,
        )

    def redo(self) -> ExternalLasInsertOutcome:
        command = self._require_command(applied=False)
        target = self._target()
        occupied = [
            curve.metadata.original_mnemonic
            for curve in command.curves
            if curve.metadata.curve_id in target.curves
            or target.curve_by_mnemonic(curve.metadata.original_mnemonic) is not None
        ]
        if occupied:
            raise RuntimeError("Мнемоники вставляемых кривых уже заняты: " + ", ".join(occupied))
        for curve in command.curves:
            target.curves[curve.metadata.curve_id] = curve
        target.parameters[command.manifest_key] = command.manifest_json
        command.applied = True
        recalculation = recalculate_existing_dependents(
            self.session,
            target,
            formula_registry=self.formula_registry,
        )
        self.session.dirty = True
        return ExternalLasInsertOutcome(
            tuple(curve.metadata.original_mnemonic for curve in command.curves),
            recalculation,
        )

    def clear_history(self) -> None:
        self._analysis = None
        self._source_dataset = None
        self._command = None

    def _target(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите LAS-приёмник")
        return dataset

    def _require_command(self, *, applied: bool) -> _ExternalLasInsertCommand:
        command = self._command
        if command is None or command.applied is not applied:
            raise RuntimeError("Нет вставки внешнего LAS для этой операции")
        if self._target().dataset_id != command.target_dataset_id:
            raise RuntimeError("История вставки относится к другому LAS")
        return command


def _next_manifest_key(dataset: Dataset) -> str:
    prefix = "EXTERNAL_LAS_IMPORT_"
    used_numbers: set[int] = set()
    for key in dataset.parameters:
        if not key.startswith(prefix):
            continue
        number_text = key[len(prefix) : len(prefix) + 3]
        if number_text.isdigit():
            used_numbers.add(int(number_text))
    number = 1
    while number in used_numbers:
        number += 1
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}{number:03d}_{timestamp}"
