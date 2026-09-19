from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from geoworkbench.domain.document_bundle import (
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.domain.models import Project, Well
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotController,
    DocumentBundleSnapshotError,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.project_file_safety import (
    FileFingerprint,
    ProjectDiskState,
)


class StaticProjectFileSafety:
    def __init__(self, state: ProjectDiskState) -> None:
        self.state = state

    def inspect(self, _source: Path) -> ProjectDiskState:
        return self.state


def _request() -> DocumentBundleRequest:
    return DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog", "gas-report"),
        languages=("ru", "en"),
        orientations=("portrait", "landscape"),
        scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
    )


def _disk_state(path: Path, *, revision: int = 3) -> ProjectDiskState:
    return ProjectDiskState(
        path=path,
        path_id="a" * 64,
        storage_kind="package",
        project_id="project-1",
        save_revision=revision,
        fingerprint=FileFingerprint(100, 200, "b" * 64, 1, 2),
        bundle_sha256="c" * 64,
    )


def _controller(*, dirty: bool = False) -> ProjectController:
    path = Path("project.geologpkg")
    well = Well("well-1", "Well", content_revision=7)
    project = Project("project-1", "Project", wells={well.well_id: well}, save_revision=3)
    controller = ProjectController(
        session=ProjectSession(
            project=project,
            current_well_id=well.well_id,
            dirty=dirty,
        )
    )
    state = _disk_state(path)
    controller.project_path = path
    controller.disk_state = state
    controller.file_safety = StaticProjectFileSafety(state)  # type: ignore[assignment]
    return controller


def test_snapshot_binding_captures_exact_saved_project_and_well_revision() -> None:
    controller = _controller()

    snapshot = DocumentBundleSnapshotController(controller).capture(_request())

    assert snapshot.request == _request()
    assert snapshot.project_path == Path("project.geologpkg")
    assert snapshot.project_id == "project-1"
    assert snapshot.save_revision == 3
    assert snapshot.well_content_revision == 7
    assert snapshot.storage_kind == "package"
    assert snapshot.path_id == "a" * 64
    assert snapshot.bundle_sha256 == "c" * 64
    assert len(snapshot.snapshot_id) == 32


def test_snapshot_binding_rejects_dirty_project() -> None:
    controller = _controller(dirty=True)

    with pytest.raises(DocumentBundleSnapshotError, match="Save the project"):
        DocumentBundleSnapshotController(controller).capture(_request())


def test_snapshot_binding_rejects_missing_verified_saved_state() -> None:
    controller = _controller()
    controller.disk_state = None

    with pytest.raises(DocumentBundleSnapshotError, match="verified saved project"):
        DocumentBundleSnapshotController(controller).capture(_request())


def test_snapshot_binding_rejects_unknown_well() -> None:
    controller = _controller()
    request = replace(_request(), well_id="missing-well")

    with pytest.raises(DocumentBundleSnapshotError, match="not present"):
        DocumentBundleSnapshotController(controller).capture(request)


def test_snapshot_binding_rejects_external_project_change() -> None:
    controller = _controller()
    assert controller.disk_state is not None
    controller.file_safety = StaticProjectFileSafety(
        replace(controller.disk_state, bundle_sha256="d" * 64)
    )  # type: ignore[assignment]

    with pytest.raises(DocumentBundleSnapshotError, match="changed externally"):
        DocumentBundleSnapshotController(controller).capture(_request())


def test_snapshot_binding_rejects_mismatched_save_revision() -> None:
    controller = _controller()
    assert controller.disk_state is not None
    controller.disk_state = replace(controller.disk_state, save_revision=2)
    controller.file_safety = StaticProjectFileSafety(
        controller.disk_state
    )  # type: ignore[assignment]

    with pytest.raises(DocumentBundleSnapshotError, match="does not match"):
        DocumentBundleSnapshotController(controller).capture(_request())
