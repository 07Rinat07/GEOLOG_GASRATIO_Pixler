"""Operator's explicit geological evidence approval -> signed PDF and Passport.

Native Qt/Report Passport cases run in separate subprocesses (#544).
"""

from __future__ import annotations

import faulthandler
import json
from pathlib import Path
import re
from types import SimpleNamespace

import fitz
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QMessageBox, QPushButton

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_passport import passport_sidecar_path
from geoworkbench.ui import interpretation_report_workspace_final as final
from test_interpretation_geology_evidence_operator_ui import _workspace
from test_interpretation_method_comparison_ui_pdf_handoff import (
    _choose_and_capture,
    _prepare_dialogs,
)


@pytest.fixture(autouse=True)
def _bounded_native_qt():
    faulthandler.dump_traceback_later(45, exit=True)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()


@pytest.fixture(autouse=True)
def _no_unexpected_modal_message(monkeypatch: pytest.MonkeyPatch):
    def unexpected(_parent, title, message, *args, **kwargs):
        del args, kwargs
        pytest.fail(f"Unexpected modal dialog {title!r}: {message}")
    for method in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, method, unexpected)


def _open_geology(workspace, qapp):
    workspace.geology_evidence_button.click()
    qapp.processEvents()
    dialog = workspace._geology_evidence_dialog
    assert dialog is not None
    select = dialog.findChild(QComboBox, "interpretation-geology-evidence-select")
    approve = dialog.findChild(QPushButton, "interpretation-geology-include-in-pdf")
    assert select is not None and approve is not None
    assert workspace._geology_pdf_evidence == ()
    return select, approve


def _approve(workspace, qapp, index=0):
    select, approve = _open_geology(workspace, qapp)
    select.setCurrentIndex(index)
    qapp.processEvents()
    approve.click()
    qapp.processEvents()
    chosen = workspace._geology_pdf_evidence
    assert len(chosen) == 1
    assert workspace._geology_pdf_source_key is not None
    return select, chosen[0]


@pytest.mark.parametrize(
    ("language", "heading"),
    (
        (AppLanguage.RU, "Фактическое пересечение газового интервала"),
        (AppLanguage.KK, "Газ аралығы мен геологиялық деректердің нақты"),
        (AppLanguage.EN, "Measured gas interval and geological evidence"),
    ),
)
def test_confirmed_observation_reaches_real_signed_pdf(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    language: AppLanguage, heading: str,
) -> None:
    workspace, session = _workspace(monkeypatch, language)
    _prepare_dialogs(monkeypatch, workspace)
    target = tmp_path / "operator-selected.pdf"
    _choose_and_capture(monkeypatch, workspace, target)
    _, selected = _approve(workspace, qapp)

    assert selected.well_id == session.current_well_id
    assert selected.gas_top == 1002.0
    assert selected.gas_bottom == 1010.0
    workspace._export_pdf()
    assert target.read_bytes().startswith(b"%PDF")
    with fitz.open(target) as pdf:
        text = re.sub(r"\s+", " ", " ".join(page.get_text() for page in pdf))
    assert heading in text
    assert "sample-in" in text
    sidecar = json.loads(passport_sidecar_path(target).read_text(encoding="utf-8"))
    assert dict(sidecar["render"]["options"])["measured_geology_intervals"] == "1"
    assert workspace._geology_pdf_evidence == (selected,)
    workspace.close()


def test_viewing_without_approval_keeps_original_export_kwargs(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, _ = _workspace(monkeypatch)
    _prepare_dialogs(monkeypatch, workspace)
    target = tmp_path / "not-selected.pdf"
    _choose_and_capture(monkeypatch, workspace, target)
    _open_geology(workspace, qapp)
    calls = []

    def capture(_session, _report, file_path, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(primary_path=file_path)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf_with_passport", capture)
    workspace._export_pdf()
    assert len(calls) == 1
    assert "geology_evidence" not in calls[0]
    assert "method_comparisons" not in calls[0]
    workspace.close()


def test_switching_candidate_requires_new_approval(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, _ = _workspace(monkeypatch)
    _prepare_dialogs(monkeypatch, workspace)
    target = tmp_path / "unselected.pdf"
    _choose_and_capture(monkeypatch, workspace, target)
    selector, chosen = _approve(workspace, qapp)
    selector.setCurrentIndex(1)
    qapp.processEvents()
    assert workspace._geology_pdf_evidence == ()
    calls = []

    def capture(_session, _report, file_path, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(primary_path=file_path)

    monkeypatch.setattr(final, "export_hydrocarbon_interpretation_pdf_with_passport", capture)
    workspace._export_pdf()
    assert len(calls) == 1
    assert "geology_evidence" not in calls[0]
    assert chosen.gas_top != workspace.report.candidates[1].top_depth
    workspace.close()


def test_changed_geology_during_identity_dialog_blocks_pdf_before_writer(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, session = _workspace(monkeypatch)
    _prepare_dialogs(monkeypatch, workspace)
    target = tmp_path / "stale-geology.pdf"
    _choose_and_capture(monkeypatch, workspace, target)
    _approve(workspace, qapp)
    identity_picker = workspace._select_report_identity

    def edited_identity(report):
        session.current_well.cuttings[0].description = "Edited after approval"
        return identity_picker(report)

    monkeypatch.setattr(workspace, "_select_report_identity", edited_identity)
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    workspace._export_pdf()
    assert len(errors) == 1
    assert "geology changed" in str(errors[0])
    assert not target.exists()
    assert not passport_sidecar_path(target).exists()
    assert workspace._geology_pdf_evidence == ()
    workspace.close()


def test_queued_threshold_invalidation_blocks_approved_pdf(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, _ = _workspace(monkeypatch)
    _prepare_dialogs(monkeypatch, workspace)
    target = tmp_path / "queued-threshold.pdf"
    _choose_and_capture(monkeypatch, workspace, target)
    _approve(workspace, qapp)
    errors = []
    monkeypatch.setattr(workspace, "_show_export_error", errors.append)
    QTimer.singleShot(
        0, lambda: workspace.threshold.setValue(workspace.threshold.value() + 0.5),
    )
    workspace._export_pdf()
    assert len(errors) == 1
    assert not target.exists()
    assert not passport_sidecar_path(target).exists()
    assert workspace._geology_pdf_evidence == ()
    workspace.close()


def test_report_refresh_revokes_pdf_approval(qapp, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, _ = _workspace(monkeypatch)
    _approve(workspace, qapp)
    workspace.refresh()
    assert workspace._geology_pdf_evidence == ()
    assert workspace._geology_pdf_source_key is None
    assert workspace._geology_evidence_dialog is None
    workspace.close()
