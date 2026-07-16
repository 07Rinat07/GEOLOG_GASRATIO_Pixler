from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.depth_axis import (
    DepthAxisReport,
    DepthResamplePlan,
    analyze_depth_resample,
    analyze_depth_axis,
    create_ascending_depth_copy,
    create_resampled_depth_copy,
)


@dataclass(slots=True)
class DepthAxisController:
    session: ProjectSession
    _resample_source_id: str | None = None
    _resampled_dataset: Dataset | None = None

    @property
    def can_undo_resample(self) -> bool:
        well = self.session.current_well
        result = self._resampled_dataset
        return bool(well is not None and result is not None and result.dataset_id in well.datasets)

    @property
    def can_redo_resample(self) -> bool:
        well = self.session.current_well
        result = self._resampled_dataset
        return bool(well is not None and result is not None and result.dataset_id not in well.datasets)

    def analyze_current(self) -> DepthAxisReport:
        return analyze_depth_axis(self._require_dataset().depth)

    def create_ascending_copy(self) -> Dataset:
        source = self._require_dataset()
        result = create_ascending_depth_copy(source)
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        well.datasets[result.dataset_id] = result
        self.session.current_dataset_id = result.dataset_id
        self.session.dirty = True
        return result

    def analyze_resample(self, start: float, stop: float, step: float) -> DepthResamplePlan:
        return analyze_depth_resample(self._require_dataset(), start, stop, step)

    def create_resampled_copy(self, plan: DepthResamplePlan) -> Dataset:
        source = self._require_dataset()
        result = create_resampled_depth_copy(source, plan)
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        well.datasets[result.dataset_id] = result
        self._resample_source_id = source.dataset_id
        self._resampled_dataset = result
        self.session.current_dataset_id = result.dataset_id
        self.session.dirty = True
        return result

    def undo_resample(self) -> None:
        well = self.session.current_well
        result = self._resampled_dataset
        if well is None or result is None or result.dataset_id not in well.datasets:
            raise RuntimeError("Нет ресэмплинга для отмены")
        del well.datasets[result.dataset_id]
        self.session.current_dataset_id = self._resample_source_id
        self.session.dirty = True

    def redo_resample(self) -> Dataset:
        well = self.session.current_well
        result = self._resampled_dataset
        if well is None or result is None or result.dataset_id in well.datasets:
            raise RuntimeError("Нет ресэмплинга для повтора")
        well.datasets[result.dataset_id] = result
        self.session.current_dataset_id = result.dataset_id
        self.session.dirty = True
        return result

    def clear_resample_history(self) -> None:
        self._resample_source_id = None
        self._resampled_dataset = None

    def _require_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return dataset
