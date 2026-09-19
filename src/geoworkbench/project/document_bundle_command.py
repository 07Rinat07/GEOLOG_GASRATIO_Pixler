from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

import numpy as np

from geoworkbench.domain.document_bundle import DocumentBundleScopeKind
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.document_bundle_recording_service import (
    RecordedDocumentBundleExecution,
)
from geoworkbench.project.document_bundle_runtime import build_document_bundle_runtime
from geoworkbench.project.document_bundle_selection import (
    DocumentBundleOutputOption,
)


class DocumentBundleCommandError(RuntimeError):
    """Typed application error for the UI-facing WELL-06 command."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DocumentBundleCommandContext:
    well_id: str
    dataset_id: str
    options: tuple[DocumentBundleOutputOption, ...]
    available_depth_range: tuple[float, float] | None


@dataclass(slots=True)
class DocumentBundleCommandController:
    """Thin UI-facing application boundary for preparing a document bundle."""

    project_controller: ProjectController

    def context(self) -> DocumentBundleCommandContext:
        session = self.project_controller.session
        well = session.current_well
        dataset = session.current_dataset
        if well is None:
            raise DocumentBundleCommandError(
                "well_required",
                "Select a well before preparing a document bundle",
            )
        if dataset is None:
            raise DocumentBundleCommandError(
                "dataset_required",
                "Select a dataset before preparing a document bundle",
            )

        # Selection is read-only and does not require an output directory.
        from geoworkbench.project.document_bundle_selection import (
            DocumentBundleSelectionController,
        )

        selection = DocumentBundleSelectionController(session)
        options = selection.masterlog_options(
            well_id=well.well_id,
            dataset_id=dataset.dataset_id,
        )
        if not options:
            raise DocumentBundleCommandError(
                "outputs_required",
                "No saved document forms are available for the selected dataset",
            )
        return DocumentBundleCommandContext(
            well_id=well.well_id,
            dataset_id=dataset.dataset_id,
            options=options,
            available_depth_range=_dataset_depth_range(dataset.active_index.values),
        )

    def execute(
        self,
        *,
        selected_outputs: tuple[DocumentBundleOutputOption, ...],
        languages: tuple[str, ...],
        orientations: tuple[str, ...],
        scope_kind: DocumentBundleScopeKind,
        top_depth: float | None,
        bottom_depth: float | None,
        allow_drafts: bool,
        output_directory: Path,
    ) -> RecordedDocumentBundleExecution:
        if not selected_outputs:
            raise DocumentBundleCommandError(
                "outputs_required",
                "Select at least one document output",
            )
        if self.project_controller.session.dirty:
            raise DocumentBundleCommandError(
                "save_required",
                "Save the project before preparing a document bundle",
            )
        if (
            self.project_controller.project_path is None
            or self.project_controller.disk_state is None
        ):
            raise DocumentBundleCommandError(
                "save_required",
                "A verified saved project is required before preparing a document bundle",
            )

        output_root = self._require_output_root(output_directory)

        runtime = build_document_bundle_runtime(
            self.project_controller,
            output_directory=output_root,
        )
        context = self.context()
        request = runtime.selection.build_request(
            well_id=context.well_id,
            selected_outputs=selected_outputs,
            languages=languages,
            orientations=orientations,
            scope_kind=scope_kind,
            top_depth=top_depth,
            bottom_depth=bottom_depth,
            allow_drafts=allow_drafts,
        )
        return runtime.service.execute(request)

    def retry_failed(
        self,
        previous: RecordedDocumentBundleExecution,
    ) -> RecordedDocumentBundleExecution:
        if previous.run.is_complete:
            raise DocumentBundleCommandError(
                "retry_not_required",
                "The document bundle is already complete",
            )
        output_root = self._require_output_root(previous.manifest_path.parent)
        runtime = build_document_bundle_runtime(
            self.project_controller,
            output_directory=output_root,
        )
        return runtime.service.retry_failed(previous)

    @staticmethod
    def _require_output_root(output_directory: Path) -> Path:
        output_root = Path(output_directory)
        if (
            not output_root.exists()
            or not output_root.is_dir()
            or output_root.is_symlink()
        ):
            raise DocumentBundleCommandError(
                "output_directory",
                "Select an existing output directory",
            )
        return output_root


def _dataset_depth_range(values: object) -> tuple[float, float] | None:
    try:
        numeric = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    finite = numeric[np.isfinite(numeric)]
    if finite.size < 2:
        return None
    top = float(np.min(finite))
    bottom = float(np.max(finite))
    if not isfinite(top) or not isfinite(bottom) or bottom <= top:
        return None
    return top, bottom
