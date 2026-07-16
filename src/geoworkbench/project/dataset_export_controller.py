from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from geoworkbench.data.las_adapter import export_las
from geoworkbench.data.las_export_plan import (
    LasExportAnalysis,
    LasExportPlan,
    LasExportVersion,
    analyze_las_export,
)
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class DatasetExportController:
    session: ProjectSession

    def default_las_plan(self) -> LasExportPlan:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        null_value: float | None = None
        raw_null = dataset.headers.get("NULL")
        if raw_null is not None:
            try:
                candidate = float(raw_null.strip().replace(",", "."))
                if isfinite(candidate):
                    null_value = candidate
            except ValueError:
                pass
        report = self.session.import_reports.get(dataset.dataset_id)
        if null_value is None and report is not None:
            null_value = report.source.null_value
        version = LasExportVersion.V2_0
        wrap = False
        declared_version = dataset.version_headers.get("VERS", "").strip()
        if declared_version.startswith("1.2"):
            version = LasExportVersion.V1_2
        elif declared_version.startswith("2"):
            version = LasExportVersion.V2_0
        wrap = dataset.version_headers.get("WRAP", "").strip().casefold() in {
            "yes",
            "y",
            "true",
            "1",
        }
        if report is not None:
            source_version = (report.source.las_version or "").strip()
            if source_version.startswith("1.2"):
                version = LasExportVersion.V1_2
            elif source_version.startswith("2"):
                version = LasExportVersion.V2_0
            wrap = (report.source.wrap or "").strip().casefold() in {"yes", "y", "true", "1"}
        return LasExportPlan(
            version=version,
            wrap=wrap,
            null_value=null_value if null_value is not None else -9999.25,
        )

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
