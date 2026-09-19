from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from uuid import uuid4

from geoworkbench.domain.document_bundle import DocumentBundleRequest
from geoworkbench.project.controller import ProjectController
from geoworkbench.storage.project_file_safety import ProjectChangedExternallyError


class DocumentBundleSnapshotError(RuntimeError):
    """Raised when a document bundle cannot bind to one verified saved revision."""


@dataclass(frozen=True, slots=True)
class DocumentBundleSnapshotBinding:
    """Identity of the exact persisted project revision used by a document bundle."""

    snapshot_id: str
    request: DocumentBundleRequest
    project_path: Path
    project_id: str
    save_revision: int
    well_content_revision: int
    storage_kind: str
    path_id: str
    bundle_sha256: str

    def __post_init__(self) -> None:
        for text_value, field_name in (
            (self.snapshot_id, "snapshot_id"),
            (self.project_id, "project_id"),
            (self.storage_kind, "storage_kind"),
        ):
            if not text_value.strip():
                raise DocumentBundleSnapshotError(f"{field_name} must not be blank")

        if not isinstance(self.project_path, Path):
            raise DocumentBundleSnapshotError("project_path must be a pathlib.Path")

        for revision_value, field_name in (
            (self.save_revision, "save_revision"),
            (self.well_content_revision, "well_content_revision"),
        ):
            if isinstance(revision_value, bool) or revision_value < 1:
                raise DocumentBundleSnapshotError(f"{field_name} must be a positive integer")

        for digest_value, field_name in (
            (self.path_id, "path_id"),
            (self.bundle_sha256, "bundle_sha256"),
        ):
            if not re.fullmatch(r"[0-9a-f]{64}", digest_value):
                raise DocumentBundleSnapshotError(
                    f"{field_name} must be a lowercase SHA-256 digest"
                )


@dataclass(slots=True)
class DocumentBundleSnapshotController:
    """Bind a validated bundle request to the current verified saved project revision."""

    project_controller: ProjectController

    def capture(self, request: DocumentBundleRequest) -> DocumentBundleSnapshotBinding:
        session = self.project_controller.session
        if session.dirty:
            raise DocumentBundleSnapshotError(
                "Save the project before preparing a document bundle"
            )

        project_path = self.project_controller.project_path
        disk_state = self.project_controller.disk_state
        if project_path is None or disk_state is None:
            raise DocumentBundleSnapshotError(
                "A verified saved project is required before preparing a document bundle"
            )

        well = session.project.wells.get(request.well_id)
        if well is None:
            raise DocumentBundleSnapshotError(
                f"Well {request.well_id!r} is not present in the saved project"
            )

        try:
            self.project_controller.assert_project_storage_current()
        except ProjectChangedExternallyError as exc:
            raise DocumentBundleSnapshotError(
                "The saved project changed externally; reopen or save a copy before export"
            ) from exc

        if (
            disk_state.project_id != session.project.project_id
            or disk_state.save_revision != session.project.save_revision
        ):
            raise DocumentBundleSnapshotError(
                "The in-memory project revision does not match the verified saved revision"
            )

        return DocumentBundleSnapshotBinding(
            snapshot_id=uuid4().hex,
            request=request,
            project_path=project_path,
            project_id=session.project.project_id,
            save_revision=session.project.save_revision,
            well_content_revision=well.content_revision,
            storage_kind=disk_state.storage_kind,
            path_id=disk_state.path_id,
            bundle_sha256=disk_state.bundle_sha256,
        )

    def assert_source_current(self, snapshot: DocumentBundleSnapshotBinding) -> None:
        """Verify that the persisted source bound to *snapshot* is still byte-identical."""

        file_safety = self.project_controller.file_safety
        if file_safety is None:
            raise DocumentBundleSnapshotError(
                "Verified project storage is unavailable for snapshot validation"
            )
        try:
            current = file_safety.inspect(snapshot.project_path)
        except Exception as exc:
            raise DocumentBundleSnapshotError(
                "The saved snapshot source cannot be verified"
            ) from exc

        expected = (
            snapshot.path_id,
            snapshot.storage_kind,
            snapshot.project_id,
            snapshot.save_revision,
            snapshot.bundle_sha256,
        )
        actual = (
            current.path_id,
            current.storage_kind,
            current.project_id,
            current.save_revision,
            current.bundle_sha256,
        )
        if actual != expected:
            raise DocumentBundleSnapshotError(
                "The saved snapshot source changed after the bundle was prepared"
            )
