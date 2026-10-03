from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256

import numpy as np

from geoworkbench.data.las_import_report import LasImportReport
from geoworkbench.data.lossless_las import LosslessLasDocument
from geoworkbench.domain.models import Dataset, Well
from geoworkbench.domain.report_composition import InterpretationReportComposition
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.dataset_merge import (
    DatasetMergeAnalysis,
    MergeOverlapPolicy,
    analyze_dataset_merge,
    create_merged_dataset,
)
from geoworkbench.services.edit_history import CommandHistory
from geoworkbench.tablet.models import TabletLayout


@dataclass(slots=True)
class _DatasetMergeCommand:
    well_id: str
    target_dataset_id: str
    merged_dataset: Dataset
    baseline_signature: str
    source_document: LosslessLasDocument | None
    import_report: LasImportReport | None
    removed_layout: TabletLayout | None = None
    removed_report_composition: InterpretationReportComposition | None = None


@dataclass(slots=True)
class _DatasetMergeHistoryCommand:
    controller: "DatasetMergeController" = field(repr=False)
    merge: _DatasetMergeCommand = field(repr=False)
    description: str
    history_domain: str = field(default="dataset_merge", init=False, repr=False)

    def execute(self) -> None:
        self.controller._redo_command(self.merge)

    def undo(self) -> None:
        self.controller._undo_command(self.merge)


@dataclass(slots=True)
class DatasetMergeController:
    session: ProjectSession
    max_commands: int = 100
    shared_history: CommandHistory | None = field(default=None, kw_only=True, repr=False)
    _history: CommandHistory = field(init=False, repr=False)

    _HISTORY_DOMAIN = "dataset_merge"

    def __post_init__(self) -> None:
        if self.max_commands < 1:
            raise ValueError("История должна хранить минимум одну команду")
        self._history = self.shared_history or CommandHistory(max_commands=self.max_commands)

    @property
    def can_undo(self) -> bool:
        command = self._history.next_undo
        return (
            isinstance(command, _DatasetMergeHistoryCommand)
            and command.history_domain == self._HISTORY_DOMAIN
        )

    @property
    def can_redo(self) -> bool:
        command = self._history.next_redo
        return (
            isinstance(command, _DatasetMergeHistoryCommand)
            and command.history_domain == self._HISTORY_DOMAIN
        )

    def available_sources(self) -> tuple[Dataset, ...]:
        target = self._target()
        return tuple(
            dataset
            for well in self.session.project.wells.values()
            for dataset in well.datasets.values()
            if dataset.dataset_id != target.dataset_id
        )

    def analyze(self, source_dataset_id: str) -> DatasetMergeAnalysis:
        return analyze_dataset_merge(self._dataset(source_dataset_id), self._target())

    def create(
        self,
        source_dataset_id: str,
        analysis: DatasetMergeAnalysis,
        *,
        overlap_policy: MergeOverlapPolicy = MergeOverlapPolicy.PRESERVE_EXISTING,
        name: str | None = None,
    ) -> Dataset:
        target = self._target()
        result = create_merged_dataset(
            self._dataset(source_dataset_id),
            target,
            analysis,
            overlap_policy=overlap_policy,
        )
        if name is not None:
            normalized = name.strip()
            if not normalized:
                raise ValueError("Имя производного dataset не должно быть пустым")
            result.name = normalized

        well = self.session.current_well
        if well is None or self.session.current_well_id is None:
            raise RuntimeError("Сначала выберите скважину-приёмник")

        source_document = self.session.source_documents.get(target.dataset_id)
        import_report = self.session.import_reports.get(target.dataset_id)
        well.datasets[result.dataset_id] = result
        if source_document is not None:
            self.session.source_documents[result.dataset_id] = source_document
        if import_report is not None:
            self.session.import_reports[result.dataset_id] = import_report

        command = _DatasetMergeCommand(
            well_id=self.session.current_well_id,
            target_dataset_id=target.dataset_id,
            merged_dataset=result,
            baseline_signature=_dataset_content_signature(result),
            source_document=source_document,
            import_report=import_report,
        )
        self.session.current_dataset_id = result.dataset_id
        self._history.record_applied(
            _DatasetMergeHistoryCommand(
                self,
                command,
                f"Сращивание dataset {result.name}",
            )
        )
        self.session.dirty = True
        return result

    def undo(self) -> None:
        self._require_history_command(redo=False)
        self._history.undo()

    def redo(self) -> Dataset:
        command = self._require_history_command(redo=True)
        self._history.redo()
        return command.merge.merged_dataset

    def clear_history(self) -> None:
        self._history.clear()

    def _undo_command(self, command: _DatasetMergeCommand) -> None:
        well = self._require_command_well(command)
        merged = command.merged_dataset
        current = well.datasets.get(merged.dataset_id)
        if current is not merged:
            raise RuntimeError("Результат сращивания был удалён или заменён вне истории команд")
        if _dataset_content_signature(merged) != command.baseline_signature:
            raise RuntimeError(
                "Результат сращивания содержит последующие правки; Undo заблокирован"
            )

        command.removed_layout = self.session.tablet_layouts.pop(merged.dataset_id, None)
        command.removed_report_composition = self.session.report_compositions.pop(
            merged.dataset_id, None
        )
        self.session.source_documents.pop(merged.dataset_id, None)
        self.session.import_reports.pop(merged.dataset_id, None)
        del well.datasets[merged.dataset_id]
        self.session.current_well_id = command.well_id
        self.session.current_dataset_id = command.target_dataset_id
        self.session.dirty = True

    def _redo_command(self, command: _DatasetMergeCommand) -> None:
        well = self._require_command_well(command)
        merged = command.merged_dataset
        if merged.dataset_id in well.datasets:
            raise RuntimeError("Идентификатор результата сращивания уже занят")

        well.datasets[merged.dataset_id] = merged
        if command.removed_layout is not None:
            self.session.tablet_layouts[merged.dataset_id] = command.removed_layout
        if command.removed_report_composition is not None:
            self.session.report_compositions[merged.dataset_id] = (
                command.removed_report_composition
            )
        if command.source_document is not None:
            self.session.source_documents[merged.dataset_id] = command.source_document
        if command.import_report is not None:
            self.session.import_reports[merged.dataset_id] = command.import_report
        self.session.current_well_id = command.well_id
        self.session.current_dataset_id = merged.dataset_id
        self.session.dirty = True

    def _require_history_command(self, *, redo: bool) -> _DatasetMergeHistoryCommand:
        command = self._history.next_redo if redo else self._history.next_undo
        if (
            not isinstance(command, _DatasetMergeHistoryCommand)
            or command.history_domain != self._HISTORY_DOMAIN
        ):
            operation = "повтора" if redo else "отмены"
            raise RuntimeError(f"Нет сращивания для {operation}")
        return command

    def _require_command_well(self, command: _DatasetMergeCommand) -> Well:
        try:
            well = self.session.project.wells[command.well_id]
        except KeyError as exc:
            raise RuntimeError("Скважина сращивания больше не существует") from exc
        if command.target_dataset_id not in well.datasets:
            raise RuntimeError("Исходный dataset сращивания больше не существует")
        return well

    def _target(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите dataset-приёмник")
        return dataset

    def _dataset(self, dataset_id: str) -> Dataset:
        for well in self.session.project.wells.values():
            if dataset_id in well.datasets:
                return well.datasets[dataset_id]
        raise KeyError(f"Dataset-источник не найден: {dataset_id}")


def _dataset_content_signature(dataset: Dataset) -> str:
    """Hash factual merged content without monotonic edit counters."""

    digest = sha256()
    for value in (dataset.name, dataset.kind.value, dataset.depth_domain.value):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    digest.update(np.asarray(dataset.depth, dtype=np.float64).tobytes())
    for collection in (dataset.version_headers, dataset.headers, dataset.parameters):
        for key, value in sorted(collection.items()):
            digest.update(key.encode("utf-8"))
            digest.update(b"\0")
            digest.update(value.encode("utf-8"))
            digest.update(b"\0")
    for curve_id, curve in dataset.curves.items():
        digest.update(curve_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(repr(curve.metadata).encode("utf-8"))
        digest.update(b"\0")
        digest.update(np.asarray(curve.values, dtype=np.float64).tobytes())
    return digest.hexdigest()
