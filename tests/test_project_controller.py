from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.data.las_import_report import LasImportReport, LasSourceSnapshot
from geoworkbench.services.depth_axis import DepthAxisReport, DepthDirection
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.storage.project_file_safety import (
    FileFingerprint,
    ProjectChangedExternallyError,
    ProjectDiskState,
    ProjectFileSafetyService,
    SafeSaveResult,
    SaveMode,
    UnsafeProjectPathError,
)
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.storage.project_repository_router import ProjectRepositoryRouter
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


class RecordingProjectFileSafety:
    def __init__(self, document: ProjectDocument, state: ProjectDiskState) -> None:
        self.document = document
        self.state = state
        self.inspect_state = state
        self.save_result: SafeSaveResult | None = None
        self.save_error: Exception | None = None
        self.opened_source: Path | None = None
        self.inspected_source: Path | None = None
        self.saved_call: tuple[
            ProjectDocument,
            Path,
            ProjectDiskState | None,
            SaveMode,
            bool,
        ] | None = None

    def open_verified(self, source: Path) -> tuple[ProjectDocument, ProjectDiskState]:
        self.opened_source = source
        return self.document, self.state

    def inspect(self, source: Path) -> ProjectDiskState:
        self.inspected_source = source
        return self.inspect_state

    def save(
        self,
        document: ProjectDocument,
        target: Path,
        *,
        expected: ProjectDiskState | None,
        mode: SaveMode,
        allow_existing_target: bool,
    ) -> SafeSaveResult:
        self.saved_call = (document, target, expected, mode, allow_existing_target)
        if self.save_error is not None:
            raise self.save_error
        assert self.save_result is not None
        return self.save_result


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


def make_disk_state(
    path: Path,
    *,
    revision: int = 1,
    bundle_sha256: str = "b" * 64,
) -> ProjectDiskState:
    return ProjectDiskState(
        path=path,
        path_id="p" * 64,
        storage_kind="package",
        project_id="project-1",
        save_revision=revision,
        fingerprint=FileFingerprint(100, 200, "f" * 64, 1, 2),
        bundle_sha256=bundle_sha256,
    )


def test_controller_opens_project_and_selects_first_dataset() -> None:
    repository = MemoryProjectRepository(make_document())
    controller = ProjectController(repository=repository)

    session = controller.open_project(Path("project.geolog.json"))

    assert session.current_well_id == "well-1"
    assert session.current_dataset_id == "dataset-1"
    assert session.current_tablet_layout is repository.document.tablet_layouts["dataset-1"]
    assert session.dirty is False
    assert controller.file_safety is None
    assert controller.disk_state is None


def test_controller_enables_file_safety_only_for_builtin_router() -> None:
    controller = ProjectController()

    assert isinstance(controller.repository, ProjectRepositoryRouter)
    assert isinstance(controller.file_safety, ProjectFileSafetyService)


def test_controller_opens_builtin_project_through_verified_storage() -> None:
    source = Path("project.geologpkg")
    document = make_document()
    state = make_disk_state(source)
    safety = RecordingProjectFileSafety(document, state)
    controller = ProjectController()
    controller.file_safety = safety  # type: ignore[assignment]

    session = controller.open_project(source)

    assert safety.opened_source == source
    assert controller.disk_state is state
    assert controller.last_save_result is None
    assert session.project is document.project
    assert session.current_dataset_id == "dataset-1"


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
    assert controller.disk_state is None
    assert controller.last_save_result is None


def test_controller_verified_save_uses_current_disk_state_and_records_result() -> None:
    source = Path("project.geologpkg")
    document = make_document()
    opened_state = make_disk_state(source)
    saved_state = make_disk_state(source, revision=2, bundle_sha256="c" * 64)
    safety = RecordingProjectFileSafety(document, opened_state)
    result = SafeSaveResult(source, saved_state, None)
    safety.save_result = result
    controller = ProjectController()
    controller.file_safety = safety  # type: ignore[assignment]
    session = controller.open_project(source)
    session.dirty = True

    saved_path = controller.save_project()

    assert saved_path == source
    assert safety.saved_call is not None
    saved_document, target, expected, mode, allow_existing = safety.saved_call
    assert saved_document.project is session.project
    assert saved_document.project.save_revision == 2
    assert target == source
    assert expected is opened_state
    assert mode is SaveMode.EXPLICIT
    assert allow_existing is False
    assert controller.disk_state is saved_state
    assert controller.last_save_result is result
    assert session.dirty is False


def test_controller_save_as_has_no_baseline_and_forwards_autosave_mode() -> None:
    source = Path("project.geologpkg")
    target = Path("copy.geologpkg")
    document = make_document()
    opened_state = make_disk_state(source)
    saved_state = replace(
        make_disk_state(target, revision=2, bundle_sha256="c" * 64),
        path_id="q" * 64,
    )
    safety = RecordingProjectFileSafety(document, opened_state)
    safety.save_result = SafeSaveResult(target, saved_state, None)
    controller = ProjectController()
    controller.file_safety = safety  # type: ignore[assignment]
    controller.open_project(source).dirty = True

    controller.save_project(
        target,
        mode=SaveMode.MATERIAL_AUTOSAVE,
        allow_existing_target=True,
    )

    assert safety.saved_call is not None
    assert safety.saved_call[1:] == (
        target,
        None,
        SaveMode.MATERIAL_AUTOSAVE,
        True,
    )
    assert controller.project_path == target
    assert controller.disk_state is saved_state


def test_controller_save_as_same_path_keeps_opened_conflict_baseline() -> None:
    source = Path("project.geologpkg")
    document = make_document()
    opened_state = make_disk_state(source)
    saved_state = make_disk_state(source, revision=2, bundle_sha256="c" * 64)
    safety = RecordingProjectFileSafety(document, opened_state)
    safety.save_result = SafeSaveResult(source, saved_state, None)
    controller = ProjectController()
    controller.file_safety = safety  # type: ignore[assignment]
    controller.open_project(source).dirty = True

    controller.save_project(source, allow_existing_target=True)

    assert safety.saved_call is not None
    assert safety.saved_call[2] is opened_state


def test_controller_verified_save_failure_restores_revision_and_keeps_dirty() -> None:
    source = Path("project.geologpkg")
    document = make_document()
    opened_state = make_disk_state(source)
    safety = RecordingProjectFileSafety(document, opened_state)
    safety.save_error = ProjectChangedExternallyError("conflict")
    controller = ProjectController()
    controller.file_safety = safety  # type: ignore[assignment]
    session = controller.open_project(source)
    session.dirty = True
    controller.last_save_result = SafeSaveResult(source, opened_state, None)

    with pytest.raises(ProjectChangedExternallyError, match="conflict"):
        controller.save_project()

    assert session.project.save_revision == 1
    assert session.dirty is True
    assert controller.project_path == source
    assert controller.disk_state is opened_state
    assert controller.last_save_result is None


def test_controller_asserts_verified_project_storage_is_current() -> None:
    source = Path("project.geologpkg")
    document = make_document()
    opened_state = make_disk_state(source)
    safety = RecordingProjectFileSafety(document, opened_state)
    controller = ProjectController()
    controller.file_safety = safety  # type: ignore[assignment]
    controller.open_project(source)
    safety.inspect_state = replace(
        opened_state,
        fingerprint=replace(opened_state.fingerprint, mtime_ns=999, inode=999),
    )

    controller.assert_project_storage_current()

    safety.inspect_state = replace(opened_state, bundle_sha256="d" * 64)
    with pytest.raises(ProjectChangedExternallyError, match="изменён"):
        controller.assert_project_storage_current()


def test_controller_maps_unsafe_inspection_to_external_change_conflict() -> None:
    source = Path("project.geologpkg")
    document = make_document()
    opened_state = make_disk_state(source)
    safety = RecordingProjectFileSafety(document, opened_state)
    controller = ProjectController()
    controller.file_safety = safety  # type: ignore[assignment]
    controller.open_project(source)

    def fail_inspect(_source: Path) -> ProjectDiskState:
        raise UnsafeProjectPathError("missing")

    safety.inspect = fail_inspect  # type: ignore[method-assign]

    with pytest.raises(ProjectChangedExternallyError, match="неизменность"):
        controller.assert_project_storage_current()


def test_controller_preserves_source_documents_across_open_and_save() -> None:
    document = make_document()
    source = parse_lossless_las(b"~A\n1\n")
    document.source_documents["dataset-1"] = source
    repository = MemoryProjectRepository(document)
    controller = ProjectController(repository=repository)

    session = controller.open_project(Path("project.geolog.json"))
    controller.save_project(Path("saved.geolog.json"))

    assert session.source_documents["dataset-1"] is source
    assert repository.document.source_documents["dataset-1"] is source


def test_controller_preserves_import_reports_across_open_and_save() -> None:
    document = make_document()
    report = LasImportReport(
        LasSourceSnapshot(Path("source.las"), 0, "0" * 64, "utf-8", "none", (), None, None, None),
        DepthAxisReport(DepthDirection.UNKNOWN, None, None, None, False, 0, 0, 0),
        (),
    )
    document.import_reports["dataset-1"] = report
    repository = MemoryProjectRepository(document)
    controller = ProjectController(repository=repository)

    session = controller.open_project(Path("project.geolog.json"))
    controller.save_project(Path("saved.geolog.json"))

    assert session.import_reports["dataset-1"] is report
    assert repository.document.import_reports["dataset-1"] is report


def test_controller_preserves_tablet_presets_across_open_and_save() -> None:
    document = make_document()
    preset = TabletLayout([TrackDefinition("curve", "Curve", TrackKind.CURVE)])
    document.tablet_presets["Standard"] = preset
    repository = MemoryProjectRepository(document)
    controller = ProjectController(repository=repository)

    session = controller.open_project(Path("project.geolog.json"))
    controller.save_project(Path("saved.geolog.json"))

    assert session.tablet_presets["Standard"] is preset
    assert repository.document.tablet_presets["Standard"] is preset


def test_controller_requires_save_path() -> None:
    controller = ProjectController(repository=MemoryProjectRepository(make_document()))

    with pytest.raises(ValueError, match="путь"):
        controller.save_project()


def test_controller_owns_dirty_state_for_open_migration() -> None:
    controller = ProjectController(repository=MemoryProjectRepository(make_document()))
    controller.session.dirty = False

    controller.mark_open_migration_required(True)
    assert controller.session.dirty is True

    controller.mark_open_migration_required(False)
    assert controller.session.dirty is False


def test_controller_selects_existing_dataset_and_owns_dirty_state() -> None:
    repository = MemoryProjectRepository(make_document())
    controller = ProjectController(repository=repository)
    controller.open_project(Path("project.geolog.json"))
    controller.session.dirty = False

    selected = controller.select_existing_dataset("dataset-1", mark_dirty=True)

    assert selected.dataset_id == "dataset-1"
    assert controller.session.current_dataset_id == "dataset-1"
    assert controller.session.dirty is True


def test_controller_rejects_unknown_existing_dataset() -> None:
    repository = MemoryProjectRepository(make_document())
    controller = ProjectController(repository=repository)
    controller.open_project(Path("project.geolog.json"))

    with pytest.raises(KeyError, match="missing"):
        controller.select_existing_dataset("missing", mark_dirty=True)
