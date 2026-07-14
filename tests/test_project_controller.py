from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind


class MemoryProjectRepository:
    def __init__(self, document: ProjectDocument) -> None:
        self.document = document
        self.saved_target: Path | None = None

    def load(self, source: Path) -> ProjectDocument:
        return self.document

    def save(self, document: ProjectDocument, target: Path) -> None:
        self.document = document
        self.saved_target = target


def make_document() -> ProjectDocument:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1.0, 2.0]),
    )
    well = Well("well-1", "Well", datasets={dataset.dataset_id: dataset})
    project = Project("project-1", "Project", wells={well.well_id: well})
    layout = TabletLayout([TrackDefinition("depth", "Глубина", TrackKind.DEPTH)])
    return ProjectDocument(project, {dataset.dataset_id: layout})


def test_controller_opens_project_and_selects_first_dataset() -> None:
    repository = MemoryProjectRepository(make_document())
    controller = ProjectController(repository=repository)

    session = controller.open_project(Path("project.geolog.json"))

    assert session.current_well_id == "well-1"
    assert session.current_dataset_id == "dataset-1"
    assert session.current_tablet_layout is repository.document.tablet_layouts["dataset-1"]
    assert session.dirty is False


def test_controller_saves_current_session_through_repository() -> None:
    repository = MemoryProjectRepository(make_document())
    session = ProjectSession(
        project=repository.document.project,
        tablet_layouts=repository.document.tablet_layouts,
        dirty=True,
    )
    controller = ProjectController(repository=repository, session=session)
    target = Path("saved.geolog.json")

    result = controller.save_project(target)

    assert result == target
    assert repository.saved_target == target
    assert repository.document.project is session.project
    assert session.dirty is False


def test_controller_requires_save_path() -> None:
    controller = ProjectController(repository=MemoryProjectRepository(make_document()))

    with pytest.raises(ValueError, match="путь"):
        controller.save_project()
