from __future__ import annotations

from pathlib import Path

from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import ProjectDocument, load_project_document


class JsonProjectRepository:
    """Versioned JSON implementation of the project persistence boundary."""

    def load(self, source: Path) -> ProjectDocument:
        return load_project_document(source)

    def save(self, document: ProjectDocument, target: Path) -> None:
        save_project(
            document.project,
            target,
            tablet_layouts=document.tablet_layouts,
            source_documents=document.source_documents,
            import_reports=document.import_reports,
        )
