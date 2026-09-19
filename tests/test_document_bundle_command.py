from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.document_bundle import (
    DocumentBundleScopeKind,
)
from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    MasterlogTemplate,
    Project,
    Well,
)
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.document_bundle_command import (
    DocumentBundleCommandController,
    DocumentBundleCommandError,
)
from geoworkbench.project.session import ProjectSession


def _project_controller(tmp_path: Path) -> ProjectController:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1000.0, 1050.0, 1100.0]),
    )
    well = Well(
        "well-1",
        "Well",
        datasets={dataset.dataset_id: dataset},
    )
    project = Project(
        "project-1",
        "Project",
        wells={well.well_id: well},
        masterlog_templates={
            "template-1": MasterlogTemplate(
                "template-1",
                "A4 Masterlog",
                page_format="A4",
            )
        },
    )
    controller = ProjectController(
        session=ProjectSession(
            project=project,
            current_well_id=well.well_id,
            current_dataset_id=dataset.dataset_id,
            dirty=False,
        )
    )
    return controller


def test_command_context_exposes_current_saved_form_choices_and_depth_range(
    tmp_path: Path,
) -> None:
    controller = _project_controller(tmp_path)
    command = DocumentBundleCommandController(controller)

    context = command.context()

    assert context.well_id == "well-1"
    assert context.dataset_id == "dataset-1"
    assert context.available_depth_range == (1000.0, 1100.0)
    assert len(context.options) == 1
    assert context.options[0].source_id == "template-1"


def test_command_context_requires_current_well(tmp_path: Path) -> None:
    controller = _project_controller(tmp_path)
    controller.session.current_well_id = None
    controller.session.current_dataset_id = None

    with pytest.raises(DocumentBundleCommandError) as error:
        DocumentBundleCommandController(controller).context()

    assert error.value.code == "well_required"


def test_command_context_requires_saved_output_form(tmp_path: Path) -> None:
    controller = _project_controller(tmp_path)
    controller.session.project.masterlog_templates.clear()

    with pytest.raises(DocumentBundleCommandError) as error:
        DocumentBundleCommandController(controller).context()

    assert error.value.code == "outputs_required"


def test_execute_rejects_dirty_project_before_runtime_creation(tmp_path: Path) -> None:
    controller = _project_controller(tmp_path)
    command = DocumentBundleCommandController(controller)
    context = command.context()
    controller.session.dirty = True
    with pytest.raises(DocumentBundleCommandError) as error:
        command.execute(
            selected_outputs=(context.options[0],),
            languages=("ru",),
            orientations=("portrait",),
            scope_kind=DocumentBundleScopeKind.WHOLE_WELL,
            top_depth=None,
            bottom_depth=None,
            allow_drafts=False,
            output_directory=tmp_path,
        )

    assert error.value.code == "save_required"


def test_execute_rejects_unverified_unsaved_project(tmp_path: Path) -> None:
    controller = _project_controller(tmp_path)
    command = DocumentBundleCommandController(controller)
    context = command.context()
    with pytest.raises(DocumentBundleCommandError) as error:
        command.execute(
            selected_outputs=(context.options[0],),
            languages=("ru",),
            orientations=("portrait",),
            scope_kind=DocumentBundleScopeKind.WHOLE_WELL,
            top_depth=None,
            bottom_depth=None,
            allow_drafts=False,
            output_directory=tmp_path,
        )

    assert error.value.code == "save_required"
