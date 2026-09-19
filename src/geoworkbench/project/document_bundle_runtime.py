from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from geoworkbench.project.controller import ProjectController
from geoworkbench.project.document_bundle_preflight import (
    DocumentBundlePreflightService,
)
from geoworkbench.project.document_bundle_recording_service import (
    RecordingDocumentBundleApplicationService,
)
from geoworkbench.project.document_bundle_selection import (
    DocumentBundleSelectionController,
)
from geoworkbench.project.document_bundle_service import (
    DefaultDocumentBundleExporterFactory,
    DocumentBundleApplicationService,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotController,
)
from geoworkbench.project.document_bundle_snapshot_reader import (
    DocumentBundleSnapshotReader,
)
from geoworkbench.project.document_bundle_translation_preflight import (
    DocumentBundleTranslationPreflightValidator,
)
from geoworkbench.project.masterlog_bundle_preflight import (
    MasterlogBundlePreflightValidator,
)


class DocumentBundleRuntimeError(RuntimeError):
    """Raised when the production WELL-06 runtime cannot be wired safely."""


@dataclass(frozen=True, slots=True)
class DocumentBundleRuntime:
    selection: DocumentBundleSelectionController
    service: RecordingDocumentBundleApplicationService
    preflight: DocumentBundlePreflightService
    snapshot_reader: DocumentBundleSnapshotReader


def build_document_bundle_runtime(
    project_controller: ProjectController,
    *,
    output_directory: Path,
) -> DocumentBundleRuntime:
    """Build one production WELL-06 object graph over verified project storage."""

    file_safety = project_controller.file_safety
    if file_safety is None:
        raise DocumentBundleRuntimeError(
            "Document bundles require the verified filesystem project repository"
        )

    output_root = Path(output_directory)
    snapshot_reader = DocumentBundleSnapshotReader(file_safety)
    preflight = DocumentBundlePreflightService(
        output_validators={
            "masterlog": MasterlogBundlePreflightValidator(snapshot_reader),
        },
        cross_validators=(
            DocumentBundleTranslationPreflightValidator(snapshot_reader),
        ),
    )
    snapshot_controller = DocumentBundleSnapshotController(project_controller)
    exporter_factory = DefaultDocumentBundleExporterFactory(
        output_directory=output_root,
        snapshot_reader=snapshot_reader,
    )
    core_service = DocumentBundleApplicationService(
        snapshot_gateway=snapshot_controller,
        exporter_factory=exporter_factory,
        preflight=preflight,
    )
    recording_service = RecordingDocumentBundleApplicationService(
        delegate=core_service,
        output_root=output_root,
    )
    return DocumentBundleRuntime(
        selection=DocumentBundleSelectionController(project_controller.session),
        service=recording_service,
        preflight=preflight,
        snapshot_reader=snapshot_reader,
    )
