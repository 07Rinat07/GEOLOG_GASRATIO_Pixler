from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.time_to_depth_conversion import (
    TimeToDepthPlan,
    TimeToDepthResult,
    convert_time_dataset_to_depth,
)


@dataclass(slots=True)
class TimeToDepthController:
    session: ProjectSession
    _source_dataset_id: str | None = None
    _result: Dataset | None = None

    def clear_history(self) -> None:
        self._source_dataset_id = None
        self._result = None

    def create_copy(self, plan: TimeToDepthPlan) -> TimeToDepthResult:
        source = self.session.current_dataset
        well = self.session.current_well
        if source is None or well is None:
            raise RuntimeError("Сначала выберите набор данных")
        converted = convert_time_dataset_to_depth(source, plan)
        well.datasets[converted.dataset.dataset_id] = converted.dataset
        self._source_dataset_id = source.dataset_id
        self._result = converted.dataset
        self.session.current_dataset_id = converted.dataset.dataset_id
        self.session.dirty = True
        return converted

    def undo(self) -> None:
        well = self.session.current_well
        if well is None or self._result is None or self._result.dataset_id not in well.datasets:
            raise RuntimeError("Нет преобразования TIME→DEPTH для отмены")
        del well.datasets[self._result.dataset_id]
        self.session.current_dataset_id = self._source_dataset_id
        self.session.dirty = True

    def redo(self) -> Dataset:
        well = self.session.current_well
        if well is None or self._result is None or self._result.dataset_id in well.datasets:
            raise RuntimeError("Нет преобразования TIME→DEPTH для повтора")
        well.datasets[self._result.dataset_id] = self._result
        self.session.current_dataset_id = self._result.dataset_id
        self.session.dirty = True
        return self._result
