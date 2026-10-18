"""Opt-in, source-guarded handoff from Qt comparison dialog to real Word report."""

from __future__ import annotations

from dataclasses import replace
import faulthandler
import os
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from PySide6.QtWidgets import QMessageBox

from geoworkbench.services.interpretation_method_comparison_html import (
    method_comparison_table,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    default_interpretation_report_identity,
)
from geoworkbench.ui import interpretation_report_workspace_drilling as drilling
from geoworkbench.ui import interpretation_report_workspace_legacy as legacy
from test_interpretation_method_comparison_chart_html import _comparison
from test_interpretation_method_comparison_explicit_ui import _workspace


_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _ci_stage(stage: str) -> None:
    """Persist last reached Qt stage in the uploaded Windows Quality artifact."""

    if not os.environ.get("CI"):
        return
    path = Path("build/ci-artifacts/quality/ui-docx-stage.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(stage + "\n")


@pytest.fixture(autouse=True)
def _dump_stack_if_gui_test_hangs():
    """Bound newly added Qt/Word acceptance tests; never weaken CI failures."""

    faulthandler.dump_traceback_later(35, exit=True)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()


@pytest.fixture(autouse=True)
def _never_open_blocking_qt_dialog(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected Qt modal dialogs must fail tests instead of timing out."""

    def reject(_parent: object, title: str, message: str, *args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail(f"Unexpected blocking QMessageBox {title!r}: {message}")

    for method in ("critical", "warning", "information", "question"):
        monkeypatch.setattr(QMessageBox, method, reject)


def _mock_report_details_dialog(monkeypatch: pytest.MonkeyPatch, workspace) -> None:
    """Real polished export requests report identity before showing file picker."""

    monkeypatch.setattr(
        workspace,
        "_select_report_identity",
        lambda report: default_interpretation_report_identity(
            report,
            workspace._report_output_language(),
            interval=workspace._report_interval(report),
        ),
    )


def _reject_modal_export_error(monkeypatch: pytest.MonkeyPatch, workspace: object) -> None:
    """Surface a real export exception; never hang Windows CI behind QMessageBox."""

    def reject(error: Exception) -> None:
        pytest.fail(
            f"Unexpected Word export error: {error!r}; "
            f"underlying cause: {error.__cause__!r}"
        )

    monkeypatch.setattr(workspace, "_show_export_error", reject)


def _assert_word_contains_comparison(path: Path, language: AppLanguage) -> None:
    projection = method_comparison_table((_comparison(),), language, depth_unit="m")
    with ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    tables = root.findall(".//" + _WORD + "tbl")
    found = []
    for table in tables:
        rows = table.findall(_WORD + "tr")
        if len(rows) < 2:
            continue
        headings = tuple(
            "".join(t.text or "" for t in cell.iter(_WORD + "t"))
            for cell in rows[0].findall(_WORD + "tc")
        )
        if headings == projection.headings:
            found.append(rows)
    assert len(found) == 1
    values = tuple(
        "".join(t.text or "" for t in cell.iter(_WORD + "t"))
        for cell in found[0][1].findall(_WORD + "tc")
    )
    assert values == projection.rows[0].cells


@pytest.mark.parametrize("language", list(AppLanguage))
def test_operator_comparison_flows_into_real_word_export(
    tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch, language: AppLanguage,
) -> None:
    _ci_stage(f"begin real-word {language.value}")
    workspace = _workspace(language)
    _ci_stage("workspace constructed")
    assert workspace.report is not None

    def companion_opus(session, **kwargs):
        del session, kwargs
        assert workspace.report is not None
        return replace(workspace.report, report_profile="opus")

    monkeypatch.setattr(legacy, "build_opus_interpretation_report", companion_opus)
    monkeypatch.setattr(
        legacy, "compare_standard_opus_reports",
        lambda standard, opus: (_comparison(),),
    )
    target = tmp_path / "selected.docx"
    monkeypatch.setattr(workspace, "_choose_target", lambda suffix, file_filter: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda path: None)
    _mock_report_details_dialog(monkeypatch, workspace)
    _reject_modal_export_error(monkeypatch, workspace)

    _ci_stage("before compare click")
    workspace.compare_methods_button.click()
    qapp.processEvents()
    _ci_stage("after compare click")
    assert workspace._comparison_source_key is not None
    _ci_stage("before docx export")
    workspace._export_docx()
    _ci_stage("after docx export")
    assert target.exists()
    _ci_stage("before docx XML inspection")
    _assert_word_contains_comparison(target, language)
    _ci_stage("after docx XML inspection")
    assert workspace._method_comparisons == (_comparison(),)
    _ci_stage("before workspace close")
    workspace.close()
    _ci_stage("after workspace close")


@pytest.mark.parametrize("language", list(AppLanguage))
def test_word_without_operator_comparison_preserves_legacy_kwargs(
    tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch, language: AppLanguage,
) -> None:
    workspace = _workspace(language)
    target = tmp_path / "normal.docx"
    monkeypatch.setattr(workspace, "_choose_target", lambda suffix, file_filter: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda path: None)
    _mock_report_details_dialog(monkeypatch, workspace)
    _reject_modal_export_error(monkeypatch, workspace)
    calls: list[dict[str, object]] = []

    def capture(report, path, **kwargs):
        del report
        calls.append(kwargs)
        return path

    monkeypatch.setattr(drilling, "export_polished_hydrocarbon_interpretation_docx", capture)
    workspace._export_docx()
    assert len(calls) == 1
    assert "method_comparisons" not in calls[0]
    assert calls[0]["language"] is language
    assert workspace._method_comparisons == ()
    workspace.close()


@pytest.mark.parametrize("invalidates", ("report", "dataset", "threshold"))
def test_stale_comparison_fails_closed_for_word_export(
    tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch, invalidates: str,
) -> None:
    workspace = _workspace()
    assert workspace.report is not None

    def companion(session, **kwargs):
        del session, kwargs
        assert workspace.report is not None
        return replace(workspace.report, report_profile="opus")

    monkeypatch.setattr(legacy, "build_opus_interpretation_report", companion)
    monkeypatch.setattr(
        legacy, "compare_standard_opus_reports",
        lambda standard, opus: (_comparison(),),
    )
    workspace.compare_methods_button.click()
    qapp.processEvents()
    assert workspace._method_comparisons

    if invalidates == "report":
        workspace.report = replace(workspace.report, generated_at="new-report-revision")
    elif invalidates == "dataset":
        dataset = workspace.controller.session.current_dataset
        assert dataset is not None
        dataset.dataset_id = "another-source-id"
    else:
        # Use the underlying numeric input rather than the control change signal.
        # That signal also clears the snapshot, but the handoff must independently
        # detect stale settings when signals were not delivered.
        workspace.threshold.blockSignals(True)
        workspace.threshold.setValue(workspace.threshold.value() + 0.5)
        workspace.threshold.blockSignals(False)

    target = tmp_path / "stale.docx"
    _mock_report_details_dialog(monkeypatch, workspace)
    monkeypatch.setattr(workspace, "_choose_target", lambda suffix, file_filter: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda path: None)
    _mock_report_details_dialog(monkeypatch, workspace)
    _reject_modal_export_error(monkeypatch, workspace)
    calls: list[dict[str, object]] = []

    def capture(report, path, **kwargs):
        del report
        calls.append(kwargs)
        return path

    monkeypatch.setattr(drilling, "export_polished_hydrocarbon_interpretation_docx", capture)
    workspace._export_docx()
    assert len(calls) == 1
    assert "method_comparisons" not in calls[0]
    assert workspace._method_comparisons == ()
    assert workspace._comparison_source_key is None
    assert workspace._comparison_dialog is None
    workspace.close()
