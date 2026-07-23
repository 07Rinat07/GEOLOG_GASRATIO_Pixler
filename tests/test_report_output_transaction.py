from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    Project,
    Well,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.report_output_transaction import (
    execute_report_output_transaction,
    recover_report_output_transaction,
    report_transaction_journal_path,
)
from geoworkbench.services.report_passport import (
    ReportKind,
    ReportPassportBuilder,
    ReportPassportRequest,
    ReportRenderSettings,
    load_report_passport,
    passport_sidecar_path,
)


def _passport(name: str = "Report"):
    dataset = Dataset(
        dataset_id="dataset-1",
        name="Dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.array([100.0, 101.0]),
    )
    curve = CurveData(
        CurveMetadata("curve-1", "C1", "C1", "ppm", "Methane", dataset.dataset_id),
        np.array([0.0, 1.0]),
    )
    dataset.curves[curve.metadata.curve_id] = curve
    well = Well("well-1", "Well", {dataset.dataset_id: dataset})
    session = ProjectSession(Project("project-1", "Project", {well.well_id: well}), well.well_id, dataset.dataset_id)
    request = ReportPassportRequest(
        ReportKind.VIEW,
        name,
        "en",
        ReportRenderSettings(renderer="test:1", output_format="pdf"),
        interval=(100.0, 101.0),
    )
    return ReportPassportBuilder().build(session, request)


def _write(payload: bytes):
    def producer(target: Path) -> Path:
        target.write_bytes(payload)
        return target

    return producer


def test_transaction_commits_output_and_fingerprinted_passport(tmp_path) -> None:
    output = tmp_path / "report.pdf"

    result = execute_report_output_transaction(output, _write(b"new-pdf"), _passport())

    assert result.output_paths == (output,)
    assert output.read_bytes() == b"new-pdf"
    assert result.passport_path == passport_sidecar_path(output)
    payload = load_report_passport(result.passport_path)
    assert payload["artifacts"] == [
        {
            "file_name": "report.pdf",
            "media_type": "application/pdf",
            "page_number": None,
            "role": "single-file",
            "sha256": result.passport.artifacts[0].sha256,
            "size_bytes": 7,
        }
    ]
    assert not report_transaction_journal_path(output).exists()
    assert not list(tmp_path.glob(".report.pdf.report-txn-*"))


def test_standard_commit_failure_rolls_back_output_and_sidecar(tmp_path, monkeypatch) -> None:
    output = tmp_path / "report.pdf"
    first = execute_report_output_transaction(output, _write(b"old"), _passport("Old"))
    old_sidecar = first.passport_path.read_bytes()

    import geoworkbench.services.report_output_transaction as module

    calls = 0
    original = module._install_operation

    def fail_on_sidecar(operation):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("sidecar install failed")
        return original(operation)

    monkeypatch.setattr(module, "_install_operation", fail_on_sidecar)

    with pytest.raises(OSError, match="sidecar install failed"):
        execute_report_output_transaction(
            output, _write(b"new"), _passport("New"), overwrite=True
        )

    assert output.read_bytes() == b"old"
    assert passport_sidecar_path(output).read_bytes() == old_sidecar
    assert not report_transaction_journal_path(output).exists()


def test_interrupted_commit_is_recovered_from_journal(tmp_path, monkeypatch) -> None:
    output = tmp_path / "report.pdf"
    first = execute_report_output_transaction(output, _write(b"old"), _passport("Old"))
    old_digest = first.passport.passport_sha256

    import geoworkbench.services.report_output_transaction as module

    class SimulatedProcessInterruption(BaseException):
        pass

    calls = 0
    original = module._install_operation

    def interrupt_on_sidecar(operation):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SimulatedProcessInterruption()
        return original(operation)

    monkeypatch.setattr(module, "_install_operation", interrupt_on_sidecar)

    with pytest.raises(SimulatedProcessInterruption):
        execute_report_output_transaction(
            output, _write(b"new"), _passport("New"), overwrite=True
        )

    assert report_transaction_journal_path(output).exists()
    assert output.read_bytes() == b"new"

    assert recover_report_output_transaction(output)
    assert output.read_bytes() == b"old"
    assert load_report_passport(passport_sidecar_path(output))["passport_sha256"] == old_digest
    assert not report_transaction_journal_path(output).exists()


def test_overwrite_removes_obsolete_numbered_pages_transactionally(tmp_path) -> None:
    output = tmp_path / "report.png"

    def pages(target: Path) -> tuple[Path, Path]:
        first = target.with_name(f"{target.stem}_page_001{target.suffix}")
        second = target.with_name(f"{target.stem}_page_002{target.suffix}")
        first.write_bytes(b"page-1")
        second.write_bytes(b"page-2")
        return first, second

    first = execute_report_output_transaction(output, pages, _passport("Pages"))
    assert len(first.output_paths) == 2

    second = execute_report_output_transaction(
        output, _write(b"single"), _passport("Single"), overwrite=True
    )

    assert second.output_paths == (output,)
    assert output.read_bytes() == b"single"
    assert not (tmp_path / "report_page_001.png").exists()
    assert not (tmp_path / "report_page_002.png").exists()


def test_interrupted_rendering_leaves_recoverable_workspace(tmp_path) -> None:
    output = tmp_path / "report.pdf"

    class SimulatedProcessInterruption(BaseException):
        pass

    def producer(target: Path) -> Path:
        target.write_bytes(b"partial")
        raise SimulatedProcessInterruption()

    with pytest.raises(SimulatedProcessInterruption):
        execute_report_output_transaction(output, producer, _passport())

    assert report_transaction_journal_path(output).exists()
    assert recover_report_output_transaction(output)
    assert not output.exists()
    assert not passport_sidecar_path(output).exists()
    assert not report_transaction_journal_path(output).exists()


def test_committed_transaction_recovery_keeps_new_pair_and_only_cleans_journal(
    tmp_path, monkeypatch
) -> None:
    output = tmp_path / "report.pdf"

    import geoworkbench.services.report_output_transaction as module

    class SimulatedProcessInterruption(BaseException):
        pass

    original_cleanup = module._cleanup_committed_transaction

    def interrupt_cleanup(journal, workspace, operations):
        raise SimulatedProcessInterruption()

    monkeypatch.setattr(module, "_cleanup_committed_transaction", interrupt_cleanup)
    with pytest.raises(SimulatedProcessInterruption):
        execute_report_output_transaction(output, _write(b"committed"), _passport("Committed"))

    assert output.read_bytes() == b"committed"
    assert report_transaction_journal_path(output).exists()
    monkeypatch.setattr(module, "_cleanup_committed_transaction", original_cleanup)

    assert recover_report_output_transaction(output)
    assert output.read_bytes() == b"committed"
    assert load_report_passport(passport_sidecar_path(output))["artifacts"][0]["size_bytes"] == 9
    assert not report_transaction_journal_path(output).exists()


def test_transaction_fingerprints_docx_and_html_exports(tmp_path) -> None:
    from geoworkbench.data.report_document_export import export_report_docx, export_report_html
    from geoworkbench.services.report_definition import (
        ReportDefinition,
        ReportIntervalMode,
        ReportIntervalSelection,
        ReportProfile,
        resolve_report_definition,
    )

    session_passport = _passport("Document")
    dataset = Dataset(
        "dataset-doc",
        "Document dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1.0, 2.0]),
    )
    dataset.curves["c1"] = CurveData(
        CurveMetadata("c1", "C1", "C1", "ppm", "Methane", dataset.dataset_id),
        np.array([0.0, np.nan]),
    )
    definition = ReportDefinition(
        "doc:1",
        "Document",
        ReportProfile.GAS,
        dataset.dataset_id,
        dataset.active_index_id or "",
        ReportIntervalSelection(ReportIntervalMode.FULL),
        language="en",
        curve_ids=("c1",),
    )
    report = resolve_report_definition(dataset, definition, require_curves=True)

    docx_output = tmp_path / "report.docx"
    html_output = tmp_path / "report.html"
    docx_result = execute_report_output_transaction(
        docx_output,
        lambda staged: export_report_docx(dataset, staged, report),
        session_passport,
    )
    html_result = execute_report_output_transaction(
        html_output,
        lambda staged: export_report_html(dataset, staged, report),
        session_passport,
    )

    docx_payload = load_report_passport(docx_result.passport_path)
    html_payload = load_report_passport(html_result.passport_path)
    assert docx_payload["artifacts"][0]["media_type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert html_payload["artifacts"][0]["media_type"] == "text/html"
    assert docx_payload["artifacts"][0]["size_bytes"] == docx_output.stat().st_size
    assert html_payload["artifacts"][0]["size_bytes"] == html_output.stat().st_size
