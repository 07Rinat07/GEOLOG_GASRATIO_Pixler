from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from geoworkbench.data.las_adapter import export_las
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class DatasetExportController:
    session: ProjectSession

    def export_current_las(self, target: Path, *, overwrite: bool = False) -> Path:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return export_las(
            dataset,
            target,
            overwrite=overwrite,
            source_document=self.session.source_documents.get(dataset.dataset_id),
        )
