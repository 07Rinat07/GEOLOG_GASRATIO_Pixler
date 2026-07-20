from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np

from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.models import TabletLayout
from geoworkbench.services.dataset_merge import (
    DatasetMergeAnalysis,
    analyze_dataset_merge,
    create_merged_dataset,
)


@dataclass(slots=True)
class DatasetMergeController:
    session: ProjectSession
    _target_dataset_id: str | None = None
    _merged_dataset: Dataset | None = None
    _merged_signature: str | None = None
    _merged_layout: TabletLayout | None = None

    @property
    def can_undo(self) -> bool:
        well = self.session.current_well
        merged = self._merged_dataset
        return bool(well is not None and merged is not None and merged.dataset_id in well.datasets)

    @property
    def can_redo(self) -> bool:
        well = self.session.current_well
        merged = self._merged_dataset
        return bool(
            well is not None and merged is not None and merged.dataset_id not in well.datasets
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

    def create(self, source_dataset_id: str, analysis: DatasetMergeAnalysis) -> Dataset:
        target = self._target()
        result = create_merged_dataset(self._dataset(source_dataset_id), target, analysis)
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину-приёмник")
        well.datasets[result.dataset_id] = result
        self._target_dataset_id = target.dataset_id
        self._merged_dataset = result
        self._merged_signature = _dataset_signature(result)
        self.session.current_dataset_id = result.dataset_id
        self.session.dirty = True
        return result

    def undo(self) -> None:
        well = self.session.current_well
        merged = self._merged_dataset
        if well is None or merged is None or merged.dataset_id not in well.datasets:
            raise RuntimeError("Нет сращивания для отмены")
        if _dataset_signature(merged) != self._merged_signature:
            raise RuntimeError(
                "Результат сращивания содержит последующие правки; Undo заблокирован"
            )
        self._merged_layout = self.session.tablet_layouts.pop(merged.dataset_id, None)
        del well.datasets[merged.dataset_id]
        self.session.current_dataset_id = self._target_dataset_id
        self.session.dirty = True

    def redo(self) -> Dataset:
        well = self.session.current_well
        merged = self._merged_dataset
        if well is None or merged is None or merged.dataset_id in well.datasets:
            raise RuntimeError("Нет сращивания для повтора")
        well.datasets[merged.dataset_id] = merged
        if self._merged_layout is not None:
            self.session.tablet_layouts[merged.dataset_id] = self._merged_layout
        self.session.current_dataset_id = merged.dataset_id
        self.session.dirty = True
        return merged

    def clear_history(self) -> None:
        self._target_dataset_id = None
        self._merged_dataset = None
        self._merged_signature = None
        self._merged_layout = None

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


def _dataset_signature(dataset: Dataset) -> str:
    digest = sha256()
    digest.update(np.asarray(dataset.depth, dtype=np.float64).tobytes())
    for collection in (dataset.version_headers, dataset.headers, dataset.parameters):
        for key, value in sorted(collection.items()):
            digest.update(key.encode("utf-8"))
            digest.update(value.encode("utf-8"))
    for curve_id, curve in dataset.curves.items():
        digest.update(curve_id.encode("utf-8"))
        digest.update(repr(curve.metadata).encode("utf-8"))
        digest.update(str(curve.version).encode("ascii"))
        digest.update(np.asarray(curve.values, dtype=np.float64).tobytes())
    return digest.hexdigest()
