from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
    DocumentBundleRequest,
    DocumentBundleScope,
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
from geoworkbench.project.document_bundle_orchestrator import (
    DocumentBundleOutputResult,
    DocumentBundleRun,
)
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.document_bundle_command import (
    DocumentBundleCommandController,
    DocumentBundleCommandError,
)
from geoworkbench.project.document_bundle_recording_service import (
    RecordedDocumentBundleExecution,
)
from geoworkbench.project.document_bundle_snapshot import DocumentBundleSnapshotBinding
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.document_bundle_manifest import (
    build_document_bundle_manifest,
    write_document_bundle_manifest,
)


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


def test_retry_rejects_complete_bundle_without_runtime_creation(tmp_path: Path) -> None:
    controller = _project_controller(tmp_path)
    previous = _recorded_execution(tmp_path, complete=True)

    with pytest.raises(DocumentBundleCommandError) as error:
        DocumentBundleCommandController(controller).retry_failed(previous)

    assert error.value.code == "retry_not_required"


def test_retry_rejects_missing_output_directory_before_runtime_creation(tmp_path: Path) -> None:
    controller = _project_controller(tmp_path)
    previous = _recorded_execution(tmp_path, complete=False)
    missing_root = tmp_path / "missing"
    previous = RecordedDocumentBundleExecution(
        run=previous.run,
        manifest=previous.manifest,
        manifest_path=missing_root / previous.manifest_path.name,
    )

    with pytest.raises(DocumentBundleCommandError) as error:
        DocumentBundleCommandController(controller).retry_failed(previous)

    assert error.value.code == "output_directory"


def _recorded_execution(
    tmp_path: Path,
    *,
    complete: bool,
) -> RecordedDocumentBundleExecution:
    snapshot = _snapshot(tmp_path)
    if complete:
        target = tmp_path / "masterlog.pdf"
        target.write_bytes(b"%PDF")
        result = DocumentBundleOutputResult(
            output_id="masterlog",
            paths=(target,),
        )
    else:
        result = DocumentBundleOutputResult(
            output_id="masterlog",
            error_message="RuntimeError: export failed",
        )
    run = DocumentBundleRun(snapshot=snapshot, results=(result,))
    manifest = build_document_bundle_manifest(run, tmp_path)
    manifest_path = write_document_bundle_manifest(manifest, tmp_path)
    return RecordedDocumentBundleExecution(
        run=run,
        manifest=manifest,
        manifest_path=manifest_path,
    )


def _snapshot(tmp_path: Path) -> DocumentBundleSnapshotBinding:
    request = DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog",),
        languages=("ru",),
        orientations=("portrait",),
        scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
        output_specs=(
            DocumentBundleOutputSpec(
                output_id="masterlog",
                exporter_kind="masterlog",
                source_id="template-1",
                dataset_id="dataset-1",
                file_format=DocumentBundleOutputFormat.PDF,
                target_name="masterlog.pdf",
            ),
        ),
    )
    return DocumentBundleSnapshotBinding(
        snapshot_id="1" * 32,
        request=request,
        project_path=tmp_path / "project.geologpkg",
        project_id="project-1",
        save_revision=4,
        well_content_revision=9,
        storage_kind="package",
        path_id="a" * 64,
        bundle_sha256="b" * 64,
    )
