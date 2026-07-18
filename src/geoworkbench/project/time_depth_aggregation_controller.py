from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import Dataset, TimeDepthMappingProfile
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.time_depth_aggregation import (
    TimeDepthAggregationPlan,
    TimeDepthAggregationResult,
    analyze_time_depth_aggregation,
    create_time_depth_aggregated_copy,
)


@dataclass(slots=True)
class TimeDepthAggregationController:
    session: ProjectSession
    _source_dataset_id: str | None = None
    _result: Dataset | None = None

    def analyze(self, profile_id: str, interval_seconds: float) -> TimeDepthAggregationPlan:
        dataset = self._require_dataset()
        profile = self._require_profile(profile_id)
        return analyze_time_depth_aggregation(dataset, profile, interval_seconds)

    def create_copy(
        self, profile_id: str, plan: TimeDepthAggregationPlan
    ) -> TimeDepthAggregationResult:
        source = self._require_dataset()
        profile = self._require_profile(profile_id)
        result = create_time_depth_aggregated_copy(source, profile, plan)
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        well.datasets[result.dataset.dataset_id] = result.dataset
        self._source_dataset_id = source.dataset_id
        self._result = result.dataset
        self.session.current_dataset_id = result.dataset.dataset_id
        self.session.dirty = True
        return result

    def undo(self) -> None:
        well = self.session.current_well
        if well is None or self._result is None or self._result.dataset_id not in well.datasets:
            raise RuntimeError("Нет TIME↔DEPTH агрегации для отмены")
        del well.datasets[self._result.dataset_id]
        self.session.current_dataset_id = self._source_dataset_id
        self.session.dirty = True

    def redo(self) -> Dataset:
        well = self.session.current_well
        if well is None or self._result is None or self._result.dataset_id in well.datasets:
            raise RuntimeError("Нет TIME↔DEPTH агрегации для повтора")
        well.datasets[self._result.dataset_id] = self._result
        self.session.current_dataset_id = self._result.dataset_id
        self.session.dirty = True
        return self._result

    def _require_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return dataset

    def _require_profile(self, profile_id: str) -> TimeDepthMappingProfile:
        try:
            return self.session.project.time_depth_mapping_profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"TIME↔DEPTH профиль не найден: {profile_id}") from exc
