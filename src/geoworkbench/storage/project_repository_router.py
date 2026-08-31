from __future__ import annotations

from pathlib import Path

from geoworkbench.storage.json_project_repository import JsonProjectRepository
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument


class ProjectRepositoryRouter:
    """Select JSON or single-file package persistence by the requested suffix."""

    def __init__(self) -> None:
        self.json = JsonProjectRepository()
        self.package = PackageProjectRepository()

    def load(self, source: Path) -> ProjectDocument:
        return self._repository(source).load(source)

    def save(self, document: ProjectDocument, target: Path) -> None:
        self._repository(target).save(document, target)

    def _repository(self, path: Path):
        return self.package if path.suffix.casefold() == ".geologpkg" else self.json
