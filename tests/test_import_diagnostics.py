from __future__ import annotations

from pathlib import Path

from geoworkbench.services.import_diagnostics import (
    ImportDiagnosticReport,
    ImportDiagnosticStage,
    diagnostic_from_exception,
    presentation_diagnostic,
)


def test_exception_diagnostic_preserves_stage_action_and_traceback(tmp_path: Path) -> None:
    source = tmp_path / "broken.las"

    try:
        raise KeyError("curve-id")
    except KeyError as exc:
        diagnostic = diagnostic_from_exception(
            source,
            ImportDiagnosticStage.REVIEW,
            exc,
            context={"channels": 73},
        )

    assert diagnostic.stage is ImportDiagnosticStage.REVIEW
    assert diagnostic.code == "import-review-failed"
    assert diagnostic.blocking is True
    assert diagnostic.exception_type == "KeyError"
    assert ("channels", "73") in diagnostic.context
    assert "KeyError" in diagnostic.technical_details

    report = ImportDiagnosticReport((diagnostic,))
    assert report.error_count == 1
    assert report.warning_count == 0
    assert "Suggested action" in report.to_text()


def test_presentation_diagnostic_states_that_imported_data_is_retained(tmp_path: Path) -> None:
    diagnostic = presentation_diagnostic(
        tmp_path / "well.las",
        TypeError("Qt.MouseButtons expected"),
        dataset_id="dataset-1",
        dataset_name="Well data",
    )

    assert diagnostic.code == "dataset-presentation-failed"
    assert "imported" in diagnostic.summary.casefold()
    assert ("dataset_id", "dataset-1") in diagnostic.context
    assert "table" in diagnostic.suggested_action.casefold()


def test_diagnostic_report_is_persisted_atomically(tmp_path: Path) -> None:
    from geoworkbench.services.import_diagnostics import (
        persist_import_diagnostic_report,
    )

    diagnostic = diagnostic_from_exception(
        tmp_path / "broken.las",
        ImportDiagnosticStage.READ_SOURCE,
        ValueError("bad row"),
    )
    target = persist_import_diagnostic_report(
        ImportDiagnosticReport((diagnostic,)), tmp_path / "diagnostics"
    )

    assert target.exists()
    assert "bad row" in target.read_text(encoding="utf-8")
    assert list(target.parent.glob("*.tmp")) == []
