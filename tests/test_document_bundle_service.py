from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pytest

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.project.document_bundle_orchestrator import DocumentBundleExporter
from geoworkbench.project.document_bundle_service import (
    DocumentBundleApplicationService,
    DocumentBundleExporterFactory,
    DocumentBundleServiceError,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)


@dataclass
class RecordingSnapshotGateway:
    snapshot: DocumentBundleSnapshotBinding
    captures: int = 0
    validations: int = 0

    def capture(
        self,
        request: DocumentBundleRequest,
    ) -> DocumentBundleSnapshotBinding:
        assert request == self.snapshot.request
        self.captures += 1
        return self.snapshot

    def assert_source_current(
        self,
        snapshot: DocumentBundleSnapshotBinding,
    ) -> None:
        assert snapshot is self.snapshot
        self.validations += 1


@dataclass
class FakeExporter:
    output_id: str
    root: Path
    fail: bool = False
    calls: int = 0

    def export(
        self,
        snapshot: DocumentBundleSnapshotBinding,
    ) -> tuple[Path, ...]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("export failed")
        path = self.root / f"{snapshot.snapshot_id}-{self.output_id}.txt"
        path.write_text(self.output_id, encoding="utf-8")
        return (path,)


@dataclass
class StaticFactory:
    exporters: Mapping[str, DocumentBundleExporter]
    builds: int = 0

    def build(
        self,
        _snapshot: DocumentBundleSnapshotBinding,
    ) -> Mapping[str, DocumentBundleExporter]:
        self.builds += 1
        return self.exporters


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


def test_application_service_captures_once_and_executes_exporters(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    gateway = RecordingSnapshotGateway(snapshot)
    exporter = FakeExporter("masterlog", tmp_path)
    factory = StaticFactory({"masterlog": exporter})
    service = DocumentBundleApplicationService(gateway, factory)

    run = service.execute(snapshot.request)

    assert run.is_complete is True
    assert run.snapshot is snapshot
    assert gateway.captures == 1
    assert gateway.validations == 1
    assert factory.builds == 1
    assert exporter.calls == 1


def test_application_service_retry_reuses_snapshot_without_recapture(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    gateway = RecordingSnapshotGateway(snapshot)
    exporter = FakeExporter("masterlog", tmp_path, fail=True)
    factory = StaticFactory({"masterlog": exporter})
    service = DocumentBundleApplicationService(gateway, factory)

    first = service.execute(snapshot.request)
    exporter.fail = False
    retried = service.retry_failed(first)

    assert first.is_complete is False
    assert retried.is_complete is True
    assert retried.snapshot is snapshot
    assert gateway.captures == 1
    assert gateway.validations == 2
    assert factory.builds == 2
    assert exporter.calls == 2


def test_retry_complete_run_is_idempotent(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    gateway = RecordingSnapshotGateway(snapshot)
    exporter = FakeExporter("masterlog", tmp_path)
    factory = StaticFactory({"masterlog": exporter})
    service = DocumentBundleApplicationService(gateway, factory)
    complete = service.execute(snapshot.request)

    retried = service.retry_failed(complete)

    assert retried is complete
    assert exporter.calls == 1
    assert gateway.captures == 1


def test_application_service_uses_factory_validation_before_output_execution(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    gateway = RecordingSnapshotGateway(snapshot)

    @dataclass
    class RejectingFactory(DocumentBundleExporterFactory):
        def build(
            self,
            _snapshot: DocumentBundleSnapshotBinding,
        ) -> Mapping[str, DocumentBundleExporter]:
            raise DocumentBundleServiceError("unsupported")

    service = DocumentBundleApplicationService(gateway, RejectingFactory())

    with pytest.raises(DocumentBundleServiceError, match="unsupported"):
        service.execute(snapshot.request)

    assert gateway.captures == 1
    assert gateway.validations == 0
