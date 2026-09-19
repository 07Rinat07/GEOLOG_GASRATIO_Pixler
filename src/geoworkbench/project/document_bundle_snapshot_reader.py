from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.storage.project_file_safety import ProjectDiskState


class DocumentBundleSnapshotReadError(RuntimeError):
    """Raised when a bound persisted snapshot cannot be reconstructed safely."""


class VerifiedProjectSnapshotReader(Protocol):
    def open_verified(
        self,
        source: Path,
    ) -> tuple[ProjectDocument, ProjectDiskState]:
        """Open a project and return its verified persisted state."""


@dataclass(frozen=True, slots=True)
class LoadedDocumentBundleSnapshot:
    binding: DocumentBundleSnapshotBinding
    document: ProjectDocument


@dataclass(slots=True)
class DocumentBundleSnapshotReader:
    """Reconstruct bundle data from the persisted revision, never from live session state."""

    storage: VerifiedProjectSnapshotReader

    def load(
        self,
        binding: DocumentBundleSnapshotBinding,
    ) -> LoadedDocumentBundleSnapshot:
        try:
            document, state = self.storage.open_verified(binding.project_path)
        except Exception as exc:
            raise DocumentBundleSnapshotReadError(
                "The bound project snapshot could not be opened and verified"
            ) from exc

        self._assert_disk_state(binding, state)

        project = document.project
        if (
            project.project_id != binding.project_id
            or project.save_revision != binding.save_revision
        ):
            raise DocumentBundleSnapshotReadError(
                "The loaded project identity or save revision does not match the bundle snapshot"
            )

        well = project.wells.get(binding.request.well_id)
        if well is None:
            raise DocumentBundleSnapshotReadError(
                "The selected well is missing from the persisted bundle snapshot"
            )
        if well.content_revision != binding.well_content_revision:
            raise DocumentBundleSnapshotReadError(
                "The persisted well content revision does not match the bundle snapshot"
            )

        return LoadedDocumentBundleSnapshot(
            binding=binding,
            document=document,
        )

    @staticmethod
    def _assert_disk_state(
        binding: DocumentBundleSnapshotBinding,
        state: ProjectDiskState,
    ) -> None:
        expected = (
            binding.path_id,
            binding.storage_kind,
            binding.project_id,
            binding.save_revision,
            binding.bundle_sha256,
        )
        actual = (
            state.path_id,
            state.storage_kind,
            state.project_id,
            state.save_revision,
            state.bundle_sha256,
        )
        if actual != expected:
            raise DocumentBundleSnapshotReadError(
                "The persisted project bytes no longer match the bundle snapshot"
            )
