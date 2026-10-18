"""Operator-verified standard/OPUS evidence in real temporary system-print PDFs.

A simulated print spooler reads the produced PDF before its temporary directory
is removed. No real Windows printer or device is needed; physical acceptance
remains a separate field gate. Every top-level Qt test is process isolated.
"""

from __future__ import annotations

from dataclasses import replace
import faulthandler
from pathlib import Path
import re

import fitz
import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_final as final
from geoworkbench.ui import interpretation_report_workspace_legacy as legacy
from test_interpretation_method_comparison_chart_html import _comparison
from test_interpretation_method_comparison_explicit_ui import _workspace


@pytest.fixture(autouse=True)
def _isolate_native_qt_lifetime():
    faulthandler.dump_traceback_later(40, exit=True)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()


@pytest.fixture(autouse=True)
def _fail_unexpected_modal_qt_message(monkeypatch: pytest.MonkeyPatch):
    def fail_dialog(_parent, title, message, *args, **kwargs):
        del args, kwargs
        pytest.fail(f"Unexpected Qt dialog {title!r}: {message}")

    for name in ("critical", "information", "warning", "question"):
        monkeypatch.setattr(QMessageBox, name, fail_dialog)


class _AcceptedPrintDialog(final.QPrintDialog):
    """Preserve real Qt range/copy settings without opening a native driver UI."""

    def exec(self):
        return QDialog.DialogCode.Accepted


def _prepare_print(monkeypatch: pytest.MonkeyPatch, workspace):
    from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
        default_interpretation_report_identity,
    )

    monkeypatch.setattr(
        workspace,
        "_select_report_identity",
        lambda report: default_interpretation_report_identity(
            report, workspace._report_output_language(),
            interval=workspace._report_interval(report),
        ),
    )
    monkeypatch.setattr(
        final.InterpretationPrintLayoutDialog,
        "exec",
        lambda _dialog: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        workspace, "_sync_preview_geology_composition",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(final, "QPrintDialog", _AcceptedPrintDialog)
    monkeypatch.setattr(
        workspace, "_show_export_error",
        lambda error: pytest.fail(f"Print error: {error!r}"),
    )


def _select_comparison(qapp, monkeypatch: pytest.MonkeyPatch, workspace):
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
    assert workspace._method_comparisons == (_comparison(),)


def _capture_spooled_pdf(monkeypatch: pytest.MonkeyPatch):
    printed: list[tuple[tuple[int, ...], str, bytes]] = []

    def capture(source, _printer, pages, **kwargs):
        del kwargs
        contents = Path(source).read_bytes()
        with fitz.open(stream=contents, filetype="pdf") as document:
            assert document.page_count >= 1
            extracted = re.sub(
                r"\s+", " ", " ".join(page.get_text() for page in document),
            )
        printed.append((tuple(pages), extracted, contents))
        return True

    monkeypatch.setattr(final, "print_pdf_page_selection", capture)
    return printed


def _assert_real_print_handoff(qapp, monkeypatch, language, status_text):
    workspace = _workspace(language)
    _prepare_print(monkeypatch, workspace)
    printed = _capture_spooled_pdf(monkeypatch)
    _select_comparison(qapp, monkeypatch, workspace)
    workspace._print_report()
    assert len(printed) == 1
    pages, text, data = printed[0]
    assert pages and data.startswith(b"%PDF")
    assert status_text in text
    assert workspace._method_comparisons == (_comparison(),)
    workspace.close()


def test_operator_comparison_in_real_print_pdf_ru(qapp, monkeypatch):
    _assert_real_print_handoff(qapp, monkeypatch, AppLanguage.RU, "Признаки согласуются")


def test_operator_comparison_in_real_print_pdf_kk(qapp, monkeypatch):
    _assert_real_print_handoff(qapp, monkeypatch, AppLanguage.KK, "Белгілер сәйкес келеді")


def test_operator_comparison_in_real_print_pdf_en(qapp, monkeypatch):
    _assert_real_print_handoff(qapp, monkeypatch, AppLanguage.EN, "Indicators agree")


def _assert_plain_print_preserves_legacy_kwargs(qapp, monkeypatch, language):
    workspace = _workspace(language)
    _prepare_print(monkeypatch, workspace)
    printed = _capture_spooled_pdf(monkeypatch)
    calls: list[dict[str, object]] = []

    def capture_report(_report, target, **kwargs):
        calls.append(kwargs)
        with fitz.open() as document:
            page = document.new_page()
            page.insert_text((72, 72), "Ordinary printer report")
            document.save(target)
        return Path(target)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", capture_report)
    workspace._print_report()
    assert len(calls) == 1
    assert "method_comparisons" not in calls[0]
    assert calls[0]["language"] is language
    assert len(printed) == 1
    assert "Ordinary printer report" in printed[0][1]
    assert workspace._method_comparisons == ()
    workspace.close()


def test_plain_system_print_retains_kwargs_ru(qapp, monkeypatch):
    _assert_plain_print_preserves_legacy_kwargs(qapp, monkeypatch, AppLanguage.RU)


def test_plain_system_print_retains_kwargs_kk(qapp, monkeypatch):
    _assert_plain_print_preserves_legacy_kwargs(qapp, monkeypatch, AppLanguage.KK)


def test_plain_system_print_retains_kwargs_en(qapp, monkeypatch):
    _assert_plain_print_preserves_legacy_kwargs(qapp, monkeypatch, AppLanguage.EN)


def _assert_stale_comparison_prints_plain(qapp, monkeypatch, invalidates):
    workspace = _workspace()
    _prepare_print(monkeypatch, workspace)
    _select_comparison(qapp, monkeypatch, workspace)
    printed = _capture_spooled_pdf(monkeypatch)
    calls: list[dict[str, object]] = []

    if invalidates == "threshold":
        workspace.threshold.blockSignals(True)
        workspace.threshold.setValue(workspace.threshold.value() + 0.5)
        workspace.threshold.blockSignals(False)
    else:
        assert workspace.report is not None
        workspace.report = replace(workspace.report, generated_at="new-report")

    def capture_report(_report, target, **kwargs):
        calls.append(kwargs)
        with fitz.open() as doc:
            doc.new_page()
            doc.save(target)
        return Path(target)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf", capture_report)
    workspace._print_report()
    assert len(calls) == 1
    assert "method_comparisons" not in calls[0]
    assert len(printed) == 1
    assert workspace._method_comparisons == ()
    assert workspace._comparison_source_key is None
    workspace.close()


def test_stale_threshold_never_enters_print_renderer(qapp, monkeypatch):
    _assert_stale_comparison_prints_plain(qapp, monkeypatch, "threshold")


def test_stale_report_never_enters_print_renderer(qapp, monkeypatch):
    _assert_stale_comparison_prints_plain(qapp, monkeypatch, "report")


def test_queued_report_replacement_in_layout_aborts_before_renderer(qapp, monkeypatch):
    workspace = _workspace()
    _prepare_print(monkeypatch, workspace)
    _select_comparison(qapp, monkeypatch, workspace)
    rendered: list[bool] = []
    errors: list[Exception] = []

    def change_report(_dialog):
        assert workspace.report is not None
        workspace.report = replace(workspace.report, generated_at="layout-event")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(final.InterpretationPrintLayoutDialog, "exec", change_report)
    monkeypatch.setattr(
        final, "export_hydrocarbon_interpretation_pdf",
        lambda *args, **kwargs: rendered.append(True),
    )
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace._print_report()
    assert rendered == []
    assert len(errors) == 1
    assert "source changed" in str(errors[0])
    workspace.close()


def test_print_driver_dialog_invalidates_comparison_before_spooling(qapp, monkeypatch):
    workspace = _workspace()
    _prepare_print(monkeypatch, workspace)
    _select_comparison(qapp, monkeypatch, workspace)
    printed = _capture_spooled_pdf(monkeypatch)
    errors: list[Exception] = []

    class _ChangingDriverDialog(_AcceptedPrintDialog):
        def exec(self):
            # Changes operator inputs after the immutable PDF was rendered.
            workspace.threshold.setValue(workspace.threshold.value() + 0.5)
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(final, "QPrintDialog", _ChangingDriverDialog)
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace._print_report()
    assert printed == []
    assert len(errors) == 1
    assert "source changed" in str(errors[0])
    assert workspace._method_comparisons == ()
    workspace.close()
