from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from geoworkbench.domain.document_bundle import (
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.project.document_bundle_orchestrator import (
    DocumentBundleOrchestrationError,
    DocumentBundleOrchestrator,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)


@dataclass
class RecordingGuard:
    calls: list[str]
    error: Exception | None = None

    def assert_source_current(self, snapshot: DocumentBundleSnapshotBinding) -> None:
        self.calls.append(snapshot.snapshot_id)
        if self.error is not None:
            raise self.error


@dataclass
class FakeExporter:
    output_id: str
    root: Path
    fail: bool = False
    calls: int = 0

    def export(self, snapshot: DocumentBundleSnapshotBinding) -> tuple[Path, ...]:
        self.calls += 1
        if self.fail:
            raise RuntimeError(f"{self.output_id} failed")
        target = self.root / f"{snapshot.snapshot_id}-{self.output_id}.txt"
        target.write_text(
            f"{snapshot.project_id}:{snapshot.save_revision}:{self.output_id}",
            encoding="utf-8",
        )
        return (target,)


def _snapshot(tmp_path: Path) -> DocumentBundleSnapshotBinding:
    request = DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog", "gas-report"),
        languages=("ru", "en"),
        orientations=("portrait", "landscape"),
        scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
    )
    return DocumentBundleSnapshotBinding(
        snapshot_id="1" * 32,
        request=request,
        project_path=tmp_path / "project.geologpkg",
        project_id="project-1",
        save_revision=4,
        well_content_revision=9,
        storage_kind="package",
        path_id="a" * 64,
        bundle_sha256="b" * 64,
    )


def test_orchestrator_uses_same_snapshot_for_every_selected_output(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    guard = RecordingGuard([])
    masterlog = FakeExporter("masterlog", tmp_path)
    gas_report = FakeExporter("gas-report", tmp_path)
    orchestrator = DocumentBundleOrchestrator(
        exporters={
            "masterlog": masterlog,
            "gas-report": gas_report,
        },
        snapshot_guard=guard,
    )

    run = orchestrator.execute(snapshot)

    assert run.is_complete is True
    assert run.failed_output_ids == ()
    assert [result.output_id for result in run.results] == [
        "masterlog",
        "gas-report",
    ]
    assert all(result.paths[0].is_file() for result in run.results)
    assert guard.calls == [snapshot.snapshot_id, snapshot.snapshot_id]


def test_orchestrator_records_one_failure_without_hiding_other_successes(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    masterlog = FakeExporter("masterlog", tmp_path, fail=True)
    gas_report = FakeExporter("gas-report", tmp_path)
    orchestrator = DocumentBundleOrchestrator(
        exporters={
            "masterlog": masterlog,
            "gas-report": gas_report,
        },
        snapshot_guard=RecordingGuard([]),
    )

    run = orchestrator.execute(snapshot)

    assert run.is_complete is False
    assert run.failed_output_ids == ("masterlog",)
    assert run.results[0].paths == ()
    assert "RuntimeError" in (run.results[0].error_message or "")
    assert run.results[1].succeeded is True
    assert run.results[1].paths[0].is_file()


def test_retry_failed_reuses_same_snapshot_and_skips_successful_outputs(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    guard = RecordingGuard([])
    masterlog = FakeExporter("masterlog", tmp_path, fail=True)
    gas_report = FakeExporter("gas-report", tmp_path)
    orchestrator = DocumentBundleOrchestrator(
        exporters={
            "masterlog": masterlog,
            "gas-report": gas_report,
        },
        snapshot_guard=guard,
    )
    first = orchestrator.execute(snapshot)
    masterlog.fail = False

    retried = orchestrator.retry_failed(first)

    assert retried.snapshot is snapshot
    assert retried.is_complete is True
    assert masterlog.calls == 2
    assert gas_report.calls == 1
    assert guard.calls == [
        snapshot.snapshot_id,
        snapshot.snapshot_id,
        snapshot.snapshot_id,
    ]


def test_orchestrator_rejects_missing_exporter_before_writing_any_output(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot(tmp_path)
    masterlog = FakeExporter("masterlog", tmp_path)
    orchestrator = DocumentBundleOrchestrator(
        exporters={"masterlog": masterlog},
        snapshot_guard=RecordingGuard([]),
    )

    with pytest.raises(DocumentBundleOrchestrationError, match="gas-report"):
        orchestrator.execute(snapshot)

    assert masterlog.calls == 0


def test_orchestrator_rejects_registration_key_mismatch(tmp_path: Path) -> None:
    snapshot = replace(
        _snapshot(tmp_path),
        request=replace(_snapshot(tmp_path).request, output_ids=("masterlog",)),
    )
    exporter = FakeExporter("other-output", tmp_path)
    orchestrator = DocumentBundleOrchestrator(
        exporters={"masterlog": exporter},
        snapshot_guard=RecordingGuard([]),
    )

    with pytest.raises(DocumentBundleOrchestrationError, match="does not match"):
        orchestrator.execute(snapshot)


def test_snapshot_guard_failure_stops_before_export(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    masterlog = FakeExporter("masterlog", tmp_path)
    gas_report = FakeExporter("gas-report", tmp_path)
    guard = RecordingGuard([], error=RuntimeError("snapshot changed"))
    orchestrator = DocumentBundleOrchestrator(
        exporters={
            "masterlog": masterlog,
            "gas-report": gas_report,
        },
        snapshot_guard=guard,
    )

    with pytest.raises(RuntimeError, match="snapshot changed"):
        orchestrator.execute(snapshot)

    assert masterlog.calls == 0
    assert gas_report.calls == 0
