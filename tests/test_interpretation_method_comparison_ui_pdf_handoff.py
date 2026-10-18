"""Production Qt -> signed PDF comparison handoff, operator opt-in only.

Each top-level test runs in a fresh process in the Windows native-heavy runner.
This isolates native Qt lifetimes without concealing the underlying issue #544.
"""

from __future__ import annotations

from dataclasses import replace
import faulthandler
import json
from pathlib import Path
import re
from types import SimpleNamespace

import fitz
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QMessageBox

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_passport import passport_sidecar_path
from geoworkbench.ui import interpretation_report_workspace_final as final
from geoworkbench.ui import interpretation_report_workspace_legacy as legacy
from test_interpretation_method_comparison_chart_html import _comparison
from test_interpretation_method_comparison_explicit_ui import _workspace


@pytest.fixture(autouse=True)
def _bounded_qt_acceptance():
    faulthandler.dump_traceback_later(40, exit=True)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()


@pytest.fixture(autouse=True)
def _no_blocking_message_box(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(_parent: object, title: str, message: str, *args: object, **kwargs: object):
        del args, kwargs
        pytest.fail(f"Unexpected modal PDF message box {title!r}: {message}")

    for name in ("critical", "warning", "information", "question"):
        monkeypatch.setattr(QMessageBox, name, reject)


def _prepare_dialogs(monkeypatch: pytest.MonkeyPatch, workspace) -> None:
    """Keep real layout choices while accepting Qt dialogs deterministically."""
    from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
        default_interpretation_report_identity,
    )

    monkeypatch.setattr(
        workspace, "_select_report_identity",
        lambda report: default_interpretation_report_identity(
            report, workspace._report_output_language(),
            interval=workspace._report_interval(report),
        ),
    )
    monkeypatch.setattr(
        final.InterpretationPrintLayoutDialog, "exec",
        lambda _dialog: QDialog.DialogCode.Accepted,
    )
    # This acceptance scope tests production export and passport rather than
    # the independently covered HTML/chart preview controller.
    monkeypatch.setattr(
        workspace, "_sync_preview_geology_composition",
        lambda *args, **kwargs: True,
    )


def _choose_and_capture(monkeypatch: pytest.MonkeyPatch, workspace, target: Path) -> None:
    monkeypatch.setattr(workspace, "_choose_target", lambda *args: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda path: None)
    monkeypatch.setattr(
        workspace, "_show_export_error",
        lambda exc: pytest.fail(f"PDF export error: {exc!r}; cause={exc.__cause__!r}"),
    )


def _select_comparison(monkeypatch: pytest.MonkeyPatch, workspace, qapp) -> None:
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


def _assert_real_pdf_handoff(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    language: AppLanguage, status_text: str,
) -> None:
    workspace = _workspace(language)
    _prepare_dialogs(monkeypatch, workspace)
    target = tmp_path / "selected.pdf"
    _choose_and_capture(monkeypatch, workspace, target)
    _select_comparison(monkeypatch, workspace, qapp)

    workspace._export_pdf()
    assert target.is_file()
    assert target.read_bytes().startswith(b"%PDF")
    with fitz.open(target) as pdf:
        assert len(pdf) >= 1
        text = re.sub(r"\\s+", " ", " ".join(page.get_text() for page in pdf))
    assert status_text in text
    assert workspace._method_comparisons == (_comparison(),)
    sidecar = json.loads(passport_sidecar_path(target).read_text(encoding="utf-8"))
    assert dict(sidecar["render"]["options"])["method_comparison_intervals"] == "1"
    workspace.close()


def test_operator_comparison_flows_into_signed_pdf_ru(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_real_pdf_handoff(
        qapp, tmp_path, monkeypatch, AppLanguage.RU, "Признаки согласуются",
    )


def test_operator_comparison_flows_into_signed_pdf_kk(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_real_pdf_handoff(
        qapp, tmp_path, monkeypatch, AppLanguage.KK, "Белгілер сәйкес келеді",
    )


def test_operator_comparison_flows_into_signed_pdf_en(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_real_pdf_handoff(
        qapp, tmp_path, monkeypatch, AppLanguage.EN, "Indicators agree",
    )


def _assert_unselected_pdf_keeps_kwargs(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: AppLanguage,
) -> None:
    workspace = _workspace(language)
    _prepare_dialogs(monkeypatch, workspace)
    target = tmp_path / "plain.pdf"
    _choose_and_capture(monkeypatch, workspace, target)
    calls: list[dict[str, object]] = []

    def capture(session, report, path, **kwargs):
        del session, report
        calls.append(kwargs)
        return SimpleNamespace(primary_path=path)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf_with_passport", capture)
    workspace._export_pdf()
    assert len(calls) == 1
    assert "method_comparisons" not in calls[0]
    assert calls[0]["language"] is language
    assert calls[0]["include_preview_marks"] is True
    assert workspace._method_comparisons == ()
    workspace.close()


def test_plain_pdf_preserves_original_api_ru(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_unselected_pdf_keeps_kwargs(qapp, tmp_path, monkeypatch, AppLanguage.RU)


def test_plain_pdf_preserves_original_api_kk(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_unselected_pdf_keeps_kwargs(qapp, tmp_path, monkeypatch, AppLanguage.KK)


def test_plain_pdf_preserves_original_api_en(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_unselected_pdf_keeps_kwargs(qapp, tmp_path, monkeypatch, AppLanguage.EN)


def _assert_stale_comparison_not_exported(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalidates: str,
) -> None:
    workspace = _workspace()
    _prepare_dialogs(monkeypatch, workspace)
    _select_comparison(monkeypatch, workspace, qapp)

    if invalidates == "report":
        assert workspace.report is not None
        workspace.report = replace(workspace.report, generated_at="replacement-report")
    elif invalidates == "dataset":
        dataset = workspace.controller.session.current_dataset
        assert dataset is not None
        dataset.dataset_id = "replacement-dataset"
    else:
        workspace.threshold.blockSignals(True)
        workspace.threshold.setValue(workspace.threshold.value() + 0.5)
        workspace.threshold.blockSignals(False)

    target = tmp_path / "stale.pdf"
    _choose_and_capture(monkeypatch, workspace, target)
    calls: list[dict[str, object]] = []

    def capture(session, report, path, **kwargs):
        del session, report
        calls.append(kwargs)
        return SimpleNamespace(primary_path=path)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf_with_passport", capture)
    workspace._export_pdf()
    assert len(calls) == 1
    assert "method_comparisons" not in calls[0]
    assert workspace._method_comparisons == ()
    assert workspace._comparison_source_key is None
    workspace.close()


def test_stale_report_never_reaches_pdf_comparison(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_stale_comparison_not_exported(qapp, tmp_path, monkeypatch, "report")


def test_stale_dataset_never_reaches_pdf_comparison(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_stale_comparison_not_exported(qapp, tmp_path, monkeypatch, "dataset")


def test_stale_threshold_never_reaches_pdf_comparison(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_stale_comparison_not_exported(qapp, tmp_path, monkeypatch, "threshold")


def test_queued_report_change_aborts_pdf_before_writer(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace()
    _prepare_dialogs(monkeypatch, workspace)
    _select_comparison(monkeypatch, workspace, qapp)
    target = tmp_path / "queued.pdf"
    _choose_and_capture(monkeypatch, workspace, target)
    calls: list[dict[str, object]] = []
    errors: list[Exception] = []

    def capture(session, report, path, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(primary_path=path)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf_with_passport", capture)
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    QTimer.singleShot(
        0,
        lambda: setattr(
            workspace, "report",
            replace(workspace.report, generated_at="queued-revision"),
        ),
    )
    workspace._export_pdf()
    assert calls == []
    assert len(errors) == 1
    assert "source changed" in str(errors[0])
    assert workspace._method_comparisons == ()
    assert workspace._comparison_source_key is None
    workspace.close()


def test_queued_threshold_change_drops_pdf_comparison(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace()
    _prepare_dialogs(monkeypatch, workspace)
    _select_comparison(monkeypatch, workspace, qapp)
    target = tmp_path / "queued-plain.pdf"
    _choose_and_capture(monkeypatch, workspace, target)
    calls: list[dict[str, object]] = []

    def capture(session, report, path, **kwargs):
        del session, report
        calls.append(kwargs)
        return SimpleNamespace(primary_path=path)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf_with_passport", capture)
    QTimer.singleShot(
        0,
        lambda: workspace.threshold.setValue(workspace.threshold.value() + 0.5),
    )
    workspace._export_pdf()
    assert len(calls) == 1
    assert "method_comparisons" not in calls[0]
    assert workspace._method_comparisons == ()
    assert workspace._comparison_source_key is None
    workspace.close()
