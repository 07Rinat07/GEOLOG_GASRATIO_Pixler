from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from geoworkbench.project.repository import ProjectRepository
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.json_project_repository import JsonProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument


@dataclass(slots=True)
class ProjectController:
    """Application workflows for opening and saving projects, independent of Qt."""

    repository: ProjectRepository = field(default_factory=JsonProjectRepository)
    session: ProjectSession = field(default_factory=ProjectSession)
    project_path: Path | None = None

    def open_project(self, source: Path) -> ProjectSession:
        document = self.repository.load(source)
        session = ProjectSession(
            project=document.project,
            tablet_layouts=document.tablet_layouts,
        )
        self._select_first_dataset(session)
        session.dirty = False
        self.session = session
        self.project_path = source
        return session

    def save_project(self, target: Path | None = None) -> Path:
        destination = target or self.project_path
        if destination is None:
            raise ValueError("Не указан путь сохранения проекта")
        document = ProjectDocument(
            project=self.session.project,
            tablet_layouts=self.session.tablet_layouts,
        )
        self.repository.save(document, destination)
        self.project_path = destination
        self.session.dirty = False
        return destination

    @staticmethod
    def _select_first_dataset(session: ProjectSession) -> None:
        for well in session.project.wells.values():
            for dataset in well.datasets.values():
                session.current_well_id = well.well_id
                session.current_dataset_id = dataset.dataset_id
                return
