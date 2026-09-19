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
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.project.document_bundle_snapshot_reader import (
    DocumentBundleSnapshotReadError,
    DocumentBundleSnapshotReader,
)
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.storage.project_file_safety import (
    FileFingerprint,
    ProjectDiskState,
)


class StaticVerifiedStorage:
    def __init__(
        self,
        document: ProjectDocument,
        state: ProjectDiskState,
    ) -> None:
        self.document = document
        self.state = state
        self.opened: list[Path] = []

    def open_verified(
        self,
        source: Path,
    ) -> tuple[ProjectDocument, ProjectDiskState]:
        self.opened.append(source)
        return self.document, self.state


def _request() -> DocumentBundleRequest:
    return DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog",),
        languages=("ru",),
        orientations=("portrait",),
        scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
    )


def _binding(path: Path) -> DocumentBundleSnapshotBinding:
    return DocumentBundleSnapshotBinding(
        snapshot_id="1" * 32,
        request=_request(),
        project_path=path,
        project_id="project-1",
        save_revision=4,
        well_content_revision=9,
        storage_kind="package",
        path_id="a" * 64,
        bundle_sha256="b" * 64,
    )


def _document(*, save_revision: int = 4, content_revision: int = 9) -> ProjectDocument:
    well = Well("well-1", "Well", content_revision=content_revision)
    project = Project(
        "project-1",
        "Project",
        wells={well.well_id: well},
        save_revision=save_revision,
    )
    return ProjectDocument(project)


def _state(path: Path, *, save_revision: int = 4) -> ProjectDiskState:
    return ProjectDiskState(
        path=path,
        path_id="a" * 64,
        storage_kind="package",
        project_id="project-1",
        save_revision=save_revision,
        fingerprint=FileFingerprint(100, 200, "c" * 64, 1, 2),
        bundle_sha256="b" * 64,
    )


def test_snapshot_reader_returns_verified_persisted_document(tmp_path: Path) -> None:
    path = tmp_path / "project.geologpkg"
    binding = _binding(path)
    document = _document()
    storage = StaticVerifiedStorage(document, _state(path))

    loaded = DocumentBundleSnapshotReader(storage).load(binding)

    assert loaded.binding is binding
    assert loaded.document is document
    assert storage.opened == [path]


def test_snapshot_reader_rejects_changed_persisted_bytes(tmp_path: Path) -> None:
    path = tmp_path / "project.geologpkg"
    binding = _binding(path)
    state = replace(_state(path), bundle_sha256="d" * 64)

    with pytest.raises(DocumentBundleSnapshotReadError, match="bytes"):
        DocumentBundleSnapshotReader(
            StaticVerifiedStorage(_document(), state)
        ).load(binding)


def test_snapshot_reader_rejects_loaded_save_revision_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "project.geologpkg"
    binding = _binding(path)

    with pytest.raises(DocumentBundleSnapshotReadError, match="save revision"):
        DocumentBundleSnapshotReader(
            StaticVerifiedStorage(_document(save_revision=5), _state(path))
        ).load(binding)


def test_snapshot_reader_rejects_well_content_revision_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "project.geologpkg"
    binding = _binding(path)

    with pytest.raises(DocumentBundleSnapshotReadError, match="content revision"):
        DocumentBundleSnapshotReader(
            StaticVerifiedStorage(
                _document(content_revision=10),
                _state(path),
            )
        ).load(binding)


def test_snapshot_reader_rejects_missing_selected_well(tmp_path: Path) -> None:
    path = tmp_path / "project.geologpkg"
    binding = _binding(path)
    document = ProjectDocument(
        Project("project-1", "Project", save_revision=4)
    )

    with pytest.raises(DocumentBundleSnapshotReadError, match="well is missing"):
        DocumentBundleSnapshotReader(
            StaticVerifiedStorage(document, _state(path))
        ).load(binding)
