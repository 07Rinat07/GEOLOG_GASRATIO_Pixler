from __future__ import annotations

from pathlib import Path

import pytest

from geoworkbench.project.controller import ProjectController
from geoworkbench.project.document_bundle_recording_service import (
    RecordingDocumentBundleApplicationService,
)
from geoworkbench.project.document_bundle_runtime import (
    DocumentBundleRuntimeError,
    build_document_bundle_runtime,
)
from geoworkbench.project.document_bundle_service import (
    DefaultDocumentBundleExporterFactory,
    DocumentBundleApplicationService,
)
from geoworkbench.project.masterlog_bundle_preflight import (
    MasterlogBundlePreflightValidator,
)


def test_runtime_composes_all_bundle_layers_over_same_verified_reader(
    tmp_path: Path,
) -> None:
    controller = ProjectController()

    runtime = build_document_bundle_runtime(
        controller,
        output_directory=tmp_path / "bundle",
    )

    assert runtime.selection.session is controller.session
    assert isinstance(runtime.service, RecordingDocumentBundleApplicationService)
    core = runtime.service.delegate
    assert isinstance(core, DocumentBundleApplicationService)
    assert core.preflight is runtime.preflight
    assert isinstance(core.exporter_factory, DefaultDocumentBundleExporterFactory)
    assert core.exporter_factory.snapshot_reader is runtime.snapshot_reader
    masterlog = runtime.preflight.output_validators["masterlog"]
    assert isinstance(masterlog, MasterlogBundlePreflightValidator)
    assert masterlog.snapshot_loader is runtime.snapshot_reader
    translation = runtime.preflight.cross_validators[0]
    assert translation.snapshot_reader is runtime.snapshot_reader


def test_runtime_rejects_controller_without_verified_file_safety(
    tmp_path: Path,
) -> None:
    controller = ProjectController()
    controller.file_safety = None

    with pytest.raises(DocumentBundleRuntimeError, match="verified filesystem"):
        build_document_bundle_runtime(
            controller,
            output_directory=tmp_path / "bundle",
        )
