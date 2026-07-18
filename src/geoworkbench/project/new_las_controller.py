from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.new_las import NewLasPlan, create_empty_las_dataset


@dataclass(slots=True)
class NewLasController:
    session: ProjectSession

    def create(self, plan: NewLasPlan) -> Dataset:
        dataset = create_empty_las_dataset(plan)
        self.session.add_dataset(dataset, well_name=plan.name)
        return dataset
