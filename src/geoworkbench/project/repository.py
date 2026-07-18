from __future__ import annotations

from pathlib import Path
from typing import Protocol

from geoworkbench.storage.project_codec import ProjectDocument


class ProjectRepository(Protocol):
    """Persistence boundary used by application-level project workflows."""

    def load(self, source: Path) -> ProjectDocument: ...

    def save(self, document: ProjectDocument, target: Path) -> None: ...
