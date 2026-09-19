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
from geoworkbench.ui.document_bundle_selection_dialog import (
    DocumentBundleDialogSelection,
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
        selection: DocumentBundleDialogSelection,
        *,
        output_directory: Path,
    ) -> RecordedDocumentBundleExecution:
        if not selection.outputs:
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

        output_root = Path(output_directory)
        if not output_root.exists() or not output_root.is_dir():
            raise DocumentBundleCommandError(
                "output_directory",
                "Select an existing output directory",
            )

        runtime = build_document_bundle_runtime(
            self.project_controller,
            output_directory=output_root,
        )
        context = self.context()
        request = runtime.selection.build_request(
            well_id=context.well_id,
            selected_outputs=selection.outputs,
            languages=selection.languages,
            orientations=selection.orientations,
            scope_kind=selection.scope_kind,
            top_depth=selection.top_depth,
            bottom_depth=selection.bottom_depth,
            allow_drafts=selection.allow_drafts,
        )
        return runtime.service.execute(request)


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
