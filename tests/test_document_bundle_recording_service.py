from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.project.document_bundle_orchestrator import (
    DocumentBundleOutputResult,
    DocumentBundleRun,
)
from geoworkbench.project.document_bundle_recording_service import (
    RecordingDocumentBundleApplicationService,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.services.document_bundle_manifest import (
    DocumentBundleManifestStatus,
)


@dataclass
class StatefulRunner:
    snapshot: DocumentBundleSnapshotBinding
    output_root: Path
    fail: bool = False
    executes: int = 0
    retries: int = 0

    def execute(self, request: DocumentBundleRequest) -> DocumentBundleRun:
        assert request == self.snapshot.request
        self.executes += 1
        return self._run()

    def retry_failed(self, previous: DocumentBundleRun) -> DocumentBundleRun:
        assert previous.snapshot is self.snapshot
        self.retries += 1
        return self._run()

    def _run(self) -> DocumentBundleRun:
        if self.fail:
            result = DocumentBundleOutputResult(
                output_id="masterlog",
                error_message="RuntimeError: export failed",
            )
        else:
            target = self.output_root / "masterlog.pdf"
            target.write_bytes(b"%PDF-recorded")
            result = DocumentBundleOutputResult(
                output_id="masterlog",
                paths=(target,),
            )
        return DocumentBundleRun(
            snapshot=self.snapshot,
            results=(result,),
        )


def _request() -> DocumentBundleRequest:
    spec = DocumentBundleOutputSpec(
        output_id="masterlog",
        exporter_kind="masterlog",
        source_id="template-1",
        dataset_id="dataset-1",
        file_format=DocumentBundleOutputFormat.PDF,
        target_name="masterlog.pdf",
    )
    return DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog",),
        languages=("ru",),
        orientations=("portrait",),
        scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
        output_specs=(spec,),
    )


def _snapshot(tmp_path: Path) -> DocumentBundleSnapshotBinding:
    return DocumentBundleSnapshotBinding(
        snapshot_id="1" * 32,
        request=_request(),
        project_path=tmp_path / "project.geologpkg",
        project_id="project-1",
        save_revision=4,
        well_content_revision=9,
        storage_kind="package",
        path_id="a" * 64,
        bundle_sha256="b" * 64,
    )


def test_recording_service_writes_complete_manifest(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    runner = StatefulRunner(snapshot, tmp_path)
    service = RecordingDocumentBundleApplicationService(runner, tmp_path)

    recorded = service.execute(snapshot.request)

    assert recorded.run.is_complete is True
    assert recorded.manifest.status is DocumentBundleManifestStatus.COMPLETE
    assert recorded.manifest.verify() is True
    assert recorded.manifest_path.is_file()
    payload = json.loads(recorded.manifest_path.read_text(encoding="utf-8"))
    assert payload["snapshot_id"] == snapshot.snapshot_id
    assert payload["status"] == "complete"
    assert runner.executes == 1
    assert runner.retries == 0


def test_retry_rewrites_same_manifest_from_partial_to_complete(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    runner = StatefulRunner(snapshot, tmp_path, fail=True)
    service = RecordingDocumentBundleApplicationService(runner, tmp_path)

    first = service.execute(snapshot.request)
    first_digest = first.manifest.manifest_sha256
    assert first.manifest.status is DocumentBundleManifestStatus.PARTIAL

    runner.fail = False
    retried = service.retry_failed(first)

    assert retried.run.snapshot is first.run.snapshot
    assert retried.manifest.status is DocumentBundleManifestStatus.COMPLETE
    assert retried.manifest_path == first.manifest_path
    assert retried.manifest.manifest_sha256 != first_digest
    payload = json.loads(retried.manifest_path.read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert runner.executes == 1
    assert runner.retries == 1


def test_retry_preserves_same_snapshot_identity(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    runner = StatefulRunner(snapshot, tmp_path, fail=True)
    service = RecordingDocumentBundleApplicationService(runner, tmp_path)
    first = service.execute(snapshot.request)

    runner.fail = False
    retried = service.retry_failed(first)

    assert retried.manifest.snapshot_id == first.manifest.snapshot_id
    assert retried.manifest.save_revision == first.manifest.save_revision
    assert (
        retried.manifest.well_content_revision
        == first.manifest.well_content_revision
    )
    assert (
        retried.manifest.project_bundle_sha256
        == first.manifest.project_bundle_sha256
    )
