"""Operator-triggered real MD gas/geology evidence in the interpretation UI.

Each native Qt acceptance function is isolated in the Windows quality runner.
No geology correlation runs in background refresh/print/export.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtWidgets import QComboBox, QMessageBox, QPushButton, QTextBrowser

from geoworkbench.domain.models import DatasetIndex, IndexRole, IndexType
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    HydrocarbonCandidateInterval,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_legacy as legacy
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace
from test_report_geology_snapshot import _session


def _candidate(top: float, bottom: float) -> HydrocarbonCandidateInterval:
    return HydrocarbonCandidateInterval(
        top_depth=top,
        bottom_depth=bottom,
        sample_count=3,
        anomaly_strength="medium",
        primary_mnemonic="C1",
        max_robust_z=3.0,
        max_primary_value=4.0,
        fluid_hypothesis="insufficient_data",
        interval_wetness=None,
        background_wetness=None,
        wetness_robust_z=None,
        interval_balance=None,
        interval_character=None,
        pixler_assessment=None,
        lba_assessments=(),
        gas_lba_correlation="gas_only",
        metrics=(),
        evidence=(),
    )


def _workspace(monkeypatch, language=AppLanguage.EN, *, with_candidates=True):
    session = _session()
    builder = legacy.build_hydrocarbon_interpretation_report

    def with_test_candidates(active_session, **kwargs):
        report = builder(active_session, **kwargs)
        candidates = (
            (_candidate(1002.0, 1010.0), _candidate(1005.0, 1010.0))
            if with_candidates else ()
        )
        return replace(report, candidates=candidates)

    monkeypatch.setattr(
        legacy, "build_hydrocarbon_interpretation_report", with_test_candidates,
    )
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(session), language=language,
    )
    return workspace, session


@pytest.mark.parametrize(
    ("language", "caption", "content"),
    (
        (AppLanguage.RU, "Сопоставить газ с геологией", "Фактическое пересечение"),
        (AppLanguage.KK, "Газды геологиямен салыстыру", "Газ аралығы мен"),
        (AppLanguage.EN, "Compare gas with geology", "Measured gas interval"),
    ),
)
def test_click_shows_measured_data_on_explicit_operator_request(
    qapp, monkeypatch, language, caption, content,
):
    workspace, session = _workspace(monkeypatch, language)
    button = workspace.geology_evidence_button
    assert button.objectName() == "interpretation-geology-evidence-action"
    assert caption in button.text()

    calls = []
    original = legacy.correlate_gas_interval_with_well_geology

    def observed(active_session, **kwargs):
        calls.append(kwargs)
        assert active_session is session
        return original(active_session, **kwargs)

    monkeypatch.setattr(
        legacy, "correlate_gas_interval_with_well_geology", observed,
    )
    workspace.refresh()
    qapp.processEvents()
    assert calls == []  # no background geology interpretation
    button.click()
    qapp.processEvents()
    assert len(calls) == 1
    assert calls[0] == {"top_depth": 1002.0, "bottom_depth": 1010.0}

    dialog = workspace._geology_evidence_dialog
    assert dialog is not None
    assert dialog.objectName() == "interpretation-geology-evidence-dialog"
    viewer = dialog.findChild(QTextBrowser, "interpretation-geology-evidence-content")
    selector = dialog.findChild(QComboBox, "interpretation-geology-evidence-select")
    assert viewer is not None and selector is not None
    displayed = viewer.toPlainText()
    assert content in displayed
    assert "sample-in" in displayed
    assert "1004.00" in displayed
    assert "1009.00" in displayed
    assert "97.0" not in displayed  # there is no calcimetry measurement
    selector.setCurrentIndex(1)
    qapp.processEvents()
    assert len(calls) == 2
    assert calls[1]["top_depth"] == 1005.0
    workspace.close()


def test_selected_geology_snapshot_is_invalidated_after_edit(
    qapp, monkeypatch,
):
    workspace, session = _workspace(monkeypatch)
    workspace.geology_evidence_button.click()
    qapp.processEvents()
    assert workspace._geology_evidence_dialog is not None
    session.current_well.cuttings[0].description = "Edited geology"
    selector = workspace._geology_evidence_dialog.findChild(
        QComboBox, "interpretation-geology-evidence-select",
    )
    selector.setCurrentIndex(1)
    qapp.processEvents()
    assert workspace._geology_evidence_dialog is None
    workspace.close()


@pytest.mark.parametrize("change", ("threshold", "lod", "output_language", "refresh"))
def test_report_input_changes_close_geology_evidence(
    qapp, monkeypatch, change,
):
    workspace, _session_ref = _workspace(monkeypatch)
    workspace.geology_evidence_button.click()
    assert workspace._geology_evidence_dialog is not None
    if change == "threshold":
        workspace.threshold.setValue(workspace.threshold.value() + 0.25)
    elif change == "lod":
        workspace.total_gas_lod.setValue(workspace.total_gas_lod.value() + 0.25)
    elif change == "output_language":
        index = workspace.report_output_language.findData(AppLanguage.RU)
        workspace.report_output_language.setCurrentIndex(index)
    else:
        workspace.refresh()
    qapp.processEvents()
    assert workspace._geology_evidence_dialog is None
    workspace.close()


def test_absent_candidate_reports_no_geology_inference(qapp, monkeypatch):
    workspace, _ = _workspace(monkeypatch, with_candidates=False)
    notifications = []
    monkeypatch.setattr(
        QMessageBox, "information",
        lambda _parent, _title, body: notifications.append(body),
    )
    workspace.geology_evidence_button.click()
    qapp.processEvents()
    assert notifications
    assert "no candidate gas intervals" in notifications[0]
    assert workspace._geology_evidence_dialog is None
    workspace.close()


def test_wrong_active_depth_axis_does_not_claim_md_intersection(qapp, monkeypatch):
    workspace, session = _workspace(monkeypatch)
    dataset = session.current_dataset
    assert dataset is not None
    dataset.add_index(
        DatasetIndex(
            "foreign-tvd", "TVD", IndexType.TVD, IndexRole.DEPTH, "m",
            dataset.depth.copy(),
        ),
        make_active=True,
    )
    workspace.geology_evidence_button.click()
    qapp.processEvents()
    # The source renderer refuses TVD and must not invent MD-aligned facts.
    if workspace._geology_evidence_dialog is not None:
        viewer = workspace._geology_evidence_dialog.findChild(
            QTextBrowser, "interpretation-geology-evidence-content",
        )
        assert viewer is not None
        assert "requires an explicit metre MD depth axis" in viewer.toPlainText()
        assert "sample-in" not in viewer.toPlainText()
    workspace.close()


def test_mixture_mode_disables_operator_geology_action(qapp, monkeypatch):
    workspace, _ = _workspace(monkeypatch)
    index = workspace.report_mode.findData("mixture_text")
    assert index >= 0
    workspace.report_mode.setCurrentIndex(index)
    workspace.refresh()
    qapp.processEvents()
    assert not workspace.geology_evidence_button.isEnabled()
    assert workspace._geology_evidence_dialog is None
    workspace.close()


@pytest.mark.parametrize(
    ("language", "field_title", "missing"),
    (
        (AppLanguage.RU, "Кальцит, %", "Нет измерений / сведений"),
        (AppLanguage.KK, "Кальцит, %", "Өлшеулер / мәліметтер жоқ"),
        (AppLanguage.EN, "Calcite, %", "No measurement / record"),
    ),
)
def test_operator_field_preview_is_explicit_and_revokes_prior_export_approval(
    qapp, monkeypatch, language, field_title, missing,
) -> None:
    workspace, session = _workspace(monkeypatch, language)
    sample = session.current_well.cuttings[0]
    sample.calcite_percent = 0.0
    sample.dolomite_percent = None
    original = repr(session.current_well)

    workspace.geology_evidence_button.click()
    qapp.processEvents()
    dialog = workspace._geology_evidence_dialog
    assert dialog is not None
    fields = dialog.findChild(
        QComboBox, "interpretation-geology-measured-field-preview",
    )
    viewer = dialog.findChild(
        QTextBrowser, "interpretation-geology-evidence-content",
    )
    approve = dialog.findChild(
        QPushButton, "interpretation-geology-include-in-pdf",
    )
    assert fields is not None and viewer is not None and approve is not None
    assert fields.currentData() is None
    assert "Покрытие отдельных измерений" not in viewer.toPlainText()
    assert "Coverage by measured field" not in viewer.toPlainText()

    def index_for(field: tuple[str, str]) -> int:
        return next(
            index for index in range(fields.count())
            if fields.itemData(index) == field
        )

    calcite = index_for(("calcimetry", "calcite_percent"))
    dolomite = index_for(("calcimetry", "dolomite_percent"))
    fields.setCurrentIndex(calcite)
    qapp.processEvents()
    assert field_title in viewer.toPlainText()
    assert "62.5%" in viewer.toPlainText()
    assert "1002.00" in viewer.toPlainText()
    assert "1009.00" in viewer.toPlainText()

    approve.click()
    assert len(workspace._geology_pdf_evidence) == 1
    fields.setCurrentIndex(dolomite)
    qapp.processEvents()
    assert workspace._geology_pdf_evidence == ()
    assert workspace._geology_pdf_source_key is None
    assert missing in viewer.toPlainText()
    assert repr(session.current_well) == original

    fields.setCurrentIndex(0)
    qapp.processEvents()
    assert fields.currentData() is None
    assert "Покрытие отдельных измерений" not in viewer.toPlainText()
    assert "Coverage by measured field" not in viewer.toPlainText()
    workspace.close()


@pytest.mark.parametrize(
    ("language", "confirmed_label"),
    (
        (AppLanguage.RU, "Поле подтверждено для HTML-предпросмотра"),
        (AppLanguage.KK, "Өлшем HTML алдын ала қарау үшін расталды"),
        (AppLanguage.EN, "Field confirmed for HTML preview"),
    ),
)
def test_operator_confirms_source_bound_field_html_without_other_exports(
    qapp, monkeypatch, language, confirmed_label,
) -> None:
    workspace, session = _workspace(monkeypatch, language)
    sample = session.current_well.cuttings[0]
    sample.calcite_percent = 0.0
    sample.dolomite_percent = None
    original = repr(session.current_well)

    workspace.geology_evidence_button.click()
    qapp.processEvents()
    dialog = workspace._geology_evidence_dialog
    assert dialog is not None
    fields = dialog.findChild(
        QComboBox, "interpretation-geology-measured-field-preview",
    )
    confirm = dialog.findChild(
        QPushButton, "interpretation-geology-confirm-field-html",
    )
    viewer = dialog.findChild(
        QTextBrowser, "interpretation-geology-evidence-content",
    )
    assert fields is not None and confirm is not None and viewer is not None
    assert not confirm.isEnabled()
    assert workspace._geology_html_field_selection is None

    calcite = next(
        index for index in range(fields.count())
        if fields.itemData(index) == ("calcimetry", "calcite_percent")
    )
    dolomite = next(
        index for index in range(fields.count())
        if fields.itemData(index) == ("calcimetry", "dolomite_percent")
    )
    assert calcite > 0 and dolomite > 0
    fields.setCurrentIndex(calcite)
    qapp.processEvents()
    assert confirm.isEnabled()
    confirm.click()
    qapp.processEvents()
    assert confirmed_label in confirm.text()
    assert workspace._geology_html_field_selection is not None
    assert "62.5%" in viewer.toPlainText()
    assert workspace._geology_pdf_evidence == ()
    assert workspace._geology_word_evidence == ()
    assert workspace._geology_excel_evidence == ()
    assert workspace._geology_print_evidence == ()
    assert repr(session.current_well) == original

    fields.setCurrentIndex(dolomite)
    qapp.processEvents()
    assert workspace._geology_html_field_selection is None
    assert confirmed_label not in confirm.text()
    confirm.click()
    qapp.processEvents()
    assert workspace._geology_html_field_selection is not None
    assert "1002.00" in viewer.toPlainText()

    sample.description = "Edited after field confirmation"
    assert workspace.report is not None
    with pytest.raises(ValueError):
        workspace._confirmed_geology_field_html_for_handoff(workspace.report)
    assert workspace._geology_html_field_selection is None
    assert workspace._geology_evidence_dialog is None
    workspace.close()
