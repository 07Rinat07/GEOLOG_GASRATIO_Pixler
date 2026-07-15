from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from geoworkbench.data.las_adapter import export_las
from geoworkbench.data.las_export_plan import LasExportAnalysis, LasExportPlan, analyze_las_export
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class DatasetExportController:
    session: ProjectSession

    def analyze_current_las_export(
        self,
        plan: LasExportPlan,
    ) -> LasExportAnalysis:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return analyze_las_export(
            dataset,
            plan,
            self.session.source_documents.get(dataset.dataset_id),
        )

    def export_current_las(
        self,
        target: Path,
        *,
        overwrite: bool = False,
        plan: LasExportPlan | None = None,
    ) -> Path:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return export_las(
            dataset,
            target,
            overwrite=overwrite,
            source_document=self.session.source_documents.get(dataset.dataset_id),
            plan=plan,
        )
