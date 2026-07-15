from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.depth_axis import (
    DepthAxisReport,
    analyze_depth_axis,
    create_ascending_depth_copy,
)


@dataclass(slots=True)
class DepthAxisController:
    session: ProjectSession

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

    def _require_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return dataset
