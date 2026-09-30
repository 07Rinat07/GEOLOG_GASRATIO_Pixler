from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from geoworkbench.data.las_adapter import import_las_with_report
from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.dataset_copy import create_dataset_copy
from geoworkbench.services.dependent_recalculation import (
    DependentRecalculationReport,
    recalculate_existing_dependents,
)
from geoworkbench.services.edit_history import CommandHistory
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
    initial_metadata: tuple[CurveMetadata, ...]
    initial_values: tuple[np.ndarray, ...]
    manifest_key: str
    previous_manifest: str | None
    manifest_json: str
    last_recalculation: DependentRecalculationReport


@dataclass(slots=True)
class _ExternalLasInsertHistoryCommand:
    controller: "ExternalLasInsertController" = field(repr=False)
    insert: _ExternalLasInsertCommand = field(repr=False)
    description: str = "Вставка внешнего LAS"
    history_domain: str = field(default="external_las_insert", init=False, repr=False)

    def execute(self) -> None:
        self.controller._redo_command(self.insert)

    def undo(self) -> None:
        self.controller._undo_command(self.insert)


@dataclass(frozen=True, slots=True)
class ExternalLasInsertOutcome:
    inserted_mnemonics: tuple[str, ...]
    recalculation: DependentRecalculationReport


@dataclass(frozen=True, slots=True)
class ExternalLasInsertCopyOutcome:
    dataset: Dataset
    inserted_mnemonics: tuple[str, ...]
    recalculation: DependentRecalculationReport


@dataclass(slots=True)
class ExternalLasInsertController:
    session: ProjectSession
    formula_registry: "FormulaProfileRegistry | None" = None
    max_commands: int = 100
    shared_history: CommandHistory | None = field(default=None, kw_only=True, repr=False)
    _analysis: ExternalLasInsertAnalysis | None = field(default=None, init=False)
    _source_dataset: Dataset | None = field(default=None, init=False)
    _history: CommandHistory = field(init=False, repr=False)

    _HISTORY_DOMAIN = "external_las_insert"

    def __post_init__(self) -> None:
        if self.max_commands < 1:
            raise ValueError("История должна хранить минимум одну команду")
        self._history = self.shared_history or CommandHistory(max_commands=self.max_commands)

    @property
    def can_undo(self) -> bool:
        return self._history_command_available(self._history.next_undo)

    @property
    def can_redo(self) -> bool:
        return self._history_command_available(self._history.next_redo)

    def analyze_file(self, path: str | Path) -> ExternalLasInsertAnalysis:
        imported = import_las_with_report(path)
        target = self._target()
        analysis, source = analyze_external_las_insert(imported, target)
        self._analysis = analysis
        self._source_dataset = source
        return analysis

    def create_copy(
        self,
        analysis: ExternalLasInsertAnalysis,
        selections: tuple[ExternalLasCurveSelection, ...],
        *,
        name: str | None = None,
    ) -> ExternalLasInsertCopyOutcome:
        """Insert curves into a new dataset, leaving both source LAS files untouched."""

        target = self._target()
        if self._analysis != analysis or self._source_dataset is None:
            raise ValueError("Сначала повторно проанализируйте внешний LAS")
        build = build_external_las_curves(self._source_dataset, target, analysis, selections)
        result = create_dataset_copy(
            target,
            name=name or f"{target.name} + {analysis.source_path.stem}",
            provenance="external-las-copy",
        )
        manifest_key = _next_manifest_key(result)
        result.parameters[manifest_key] = build.manifest_json
        inserted: list[str] = []
        for built_curve in build.curves:
            metadata = built_curve.metadata
            curve_id = metadata.curve_id
            result.curves[curve_id] = CurveData(
                metadata=type(metadata)(
                    curve_id=curve_id,
                    original_mnemonic=metadata.original_mnemonic,
                    canonical_mnemonic=metadata.canonical_mnemonic,
                    unit=metadata.unit,
                    description=metadata.description,
                    source_dataset_id=result.dataset_id,
                    provenance=metadata.provenance,
                ),
                values=built_curve.values.copy(),
            )
            inserted.append(metadata.original_mnemonic)

        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину-приёмник")
        well.datasets[result.dataset_id] = result
        source_document = self.session.source_documents.get(target.dataset_id)
        import_report = self.session.import_reports.get(target.dataset_id)
        if source_document is not None:
            self.session.source_documents[result.dataset_id] = source_document
        if import_report is not None:
            self.session.import_reports[result.dataset_id] = import_report
        self.session.current_dataset_id = result.dataset_id
        recalculation = recalculate_existing_dependents(
            self.session,
            result,
            formula_registry=self.formula_registry,
        )
        self.session.dirty = True
        return ExternalLasInsertCopyOutcome(result, tuple(inserted), recalculation)

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
        recalculation = recalculate_existing_dependents(
            self.session,
            target,
            formula_registry=self.formula_registry,
        )
        command = _ExternalLasInsertCommand(
            target_dataset_id=target.dataset_id,
            source_path=analysis.source_path,
            curves=build.curves,
            initial_metadata=tuple(deepcopy(curve.metadata) for curve in build.curves),
            initial_values=tuple(curve.values.copy() for curve in build.curves),
            manifest_key=manifest_key,
            previous_manifest=previous,
            manifest_json=build.manifest_json,
            last_recalculation=recalculation,
        )
        self._history.record_applied(_ExternalLasInsertHistoryCommand(self, command))
        self.session.dirty = True
        return self._outcome(command)

    def undo(self) -> ExternalLasInsertOutcome:
        history_command = self._require_history_command(redo=False)
        self._history.undo()
        return self._outcome(history_command.insert)

    def redo(self) -> ExternalLasInsertOutcome:
        history_command = self._require_history_command(redo=True)
        self._history.redo()
        return self._outcome(history_command.insert)

    def clear_history(self) -> None:
        self._analysis = None
        self._source_dataset = None
        self._history.clear()

    def _undo_command(self, command: _ExternalLasInsertCommand) -> None:
        target = self._require_command_target(command)
        for curve, initial_metadata, original_values in zip(
            command.curves,
            command.initial_metadata,
            command.initial_values,
            strict=True,
        ):
            current = target.curves.get(curve.metadata.curve_id)
            if current is not curve:
                raise RuntimeError("Вставленная кривая была удалена или заменена вне истории")
            if curve.metadata != initial_metadata or not np.array_equal(
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
        command.last_recalculation = recalculate_existing_dependents(
            self.session,
            target,
            formula_registry=self.formula_registry,
        )
        self.session.dirty = True

    def _redo_command(self, command: _ExternalLasInsertCommand) -> None:
        target = self._require_command_target(command)
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
        command.last_recalculation = recalculate_existing_dependents(
            self.session,
            target,
            formula_registry=self.formula_registry,
        )
        self.session.dirty = True

    def _history_command_available(self, command: object) -> bool:
        target = self.session.current_dataset
        return bool(
            isinstance(command, _ExternalLasInsertHistoryCommand)
            and command.history_domain == self._HISTORY_DOMAIN
            and target is not None
            and target.dataset_id == command.insert.target_dataset_id
        )

    def _require_history_command(self, *, redo: bool) -> _ExternalLasInsertHistoryCommand:
        command = self._history.next_redo if redo else self._history.next_undo
        if not self._history_command_available(command):
            operation = "повтора" if redo else "отмены"
            raise RuntimeError(f"Нет вставки внешнего LAS для {operation}")
        assert isinstance(command, _ExternalLasInsertHistoryCommand)
        return command

    def _require_command_target(self, command: _ExternalLasInsertCommand) -> Dataset:
        target = self._target()
        if target.dataset_id != command.target_dataset_id:
            raise RuntimeError("История вставки относится к другому LAS")
        return target

    @staticmethod
    def _outcome(command: _ExternalLasInsertCommand) -> ExternalLasInsertOutcome:
        return ExternalLasInsertOutcome(
            tuple(curve.metadata.original_mnemonic for curve in command.curves),
            command.last_recalculation,
        )

    def _target(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите LAS-приёмник")
        return dataset


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
