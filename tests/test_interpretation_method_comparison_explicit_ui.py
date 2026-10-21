"""Operator-gated standard/OPUS comparison: no implicit second interpretation."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtWidgets import QMessageBox, QTextBrowser

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.services.interpretation_method_comparison import (
    compare_standard_opus_reports,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_legacy as legacy
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace
from test_interpretation_method_comparison_chart_html import _comparison
from test_readable_interpretation_export import _session_with_zero_heavy_components


def _workspace(language: AppLanguage = AppLanguage.RU) -> InterpretationReportWorkspace:
    session = _session_with_zero_heavy_components()
    return InterpretationReportWorkspace(
        InterpretationCalculationController(session), language=language,
    )


@pytest.mark.parametrize(
    ("language", "label"),
    (
        (AppLanguage.RU, "Сопоставить стандартный метод и ОПУС"),
        (AppLanguage.KK, "Стандартты әдіс пен ОПУС-ты салыстыру"),
        (AppLanguage.EN, "Compare standard method and OPUS"),
    ),
)
def test_comparison_action_is_explicit_not_a_refresh_side_effect(
    qapp, monkeypatch: pytest.MonkeyPatch, language: AppLanguage, label: str,
) -> None:
    workspace = _workspace(language)
    button = workspace.compare_methods_button
    assert button.objectName() == "interpretation-compare-standard-opus"
    assert button.text() == label
    calls = []

    def forbidden(*args: object, **kwargs: object):
        calls.append((args, kwargs))
        raise AssertionError("Comparison must not run in refresh/preview")

    monkeypatch.setattr(legacy, "compare_standard_opus_reports", forbidden)
    workspace.refresh()
    qapp.processEvents()
    assert calls == []
    assert workspace._method_comparisons == ()
    workspace.close()


def test_click_computes_one_validated_pair_and_shows_localized_evidence(
    qapp, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(AppLanguage.EN)
    assert workspace.report is not None
    observed = []

    def opus_report(session, **kwargs):
        assert session is workspace.controller.session
        observed.append(("opus", kwargs))
        assert workspace.report is not None
        return replace(workspace.report, report_profile="opus")

    def compare(standard, opus):
        assert standard.report_profile == "standard"
        assert opus.report_profile == "opus"
        assert standard.dataset_id == opus.dataset_id
        assert standard.depth_axis_id == opus.depth_axis_id
        observed.append(("compare", {}))
        return (_comparison(),)

    monkeypatch.setattr(legacy, "build_opus_interpretation_report", opus_report)
    monkeypatch.setattr(legacy, "compare_standard_opus_reports", compare)
    workspace.compare_methods_button.click()
    qapp.processEvents()

    assert [name for name, _ in observed] == ["opus", "compare"]
    assert workspace._method_comparisons == (_comparison(),)
    dialog = workspace._comparison_dialog
    assert dialog is not None
    assert dialog.objectName() == "interpretation-method-comparison-dialog"
    viewer = dialog.findChild(QTextBrowser, "interpretation-method-comparison-content")
    assert viewer is not None
    text = viewer.toPlainText()
    assert "Standard and OPUS method comparison" in text
    assert "Indicators agree" in text
    assert "100.00" in text

    # Refresh invalidates evidence even if the source remains loaded.
    workspace.refresh()
    qapp.processEvents()
    assert workspace._method_comparisons == ()
    assert workspace._comparison_dialog is None
    workspace.close()


def test_axis_mismatch_is_rejected_without_any_stale_comparison(
    qapp, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace()
    assert workspace.report is not None
    warnings: list[str] = []

    def incompatible_opus(session, **kwargs):
        del session, kwargs
        assert workspace.report is not None
        return replace(
            workspace.report, report_profile="opus", depth_axis_id="unrelated-axis",
        )

    def warning(_parent, _title, text):
        warnings.append(text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(legacy, "build_opus_interpretation_report", incompatible_opus)
    monkeypatch.setattr(QMessageBox, "warning", warning)
    workspace.compare_methods_button.click()
    qapp.processEvents()
    assert warnings
    assert workspace._method_comparisons == ()
    assert workspace._comparison_dialog is None
    workspace.close()


@pytest.mark.parametrize("change", ("language", "threshold", "lod"))
def test_paired_evidence_is_invalidated_on_relevant_control_change(
    qapp, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    workspace = _workspace(AppLanguage.RU)
    assert workspace.report is not None

    def opus_report(session, **kwargs):
        del session, kwargs
        assert workspace.report is not None
        return replace(workspace.report, report_profile="opus")

    monkeypatch.setattr(legacy, "build_opus_interpretation_report", opus_report)
    monkeypatch.setattr(
        legacy, "compare_standard_opus_reports",
        lambda standard, opus: (_comparison(),),
    )
    workspace.compare_methods_button.click()
    qapp.processEvents()
    assert workspace._method_comparisons
    assert workspace._comparison_dialog is not None

    if change == "language":
        index = workspace.report_output_language.findData(AppLanguage.EN)
        workspace.report_output_language.setCurrentIndex(index)
    elif change == "threshold":
        workspace.threshold.setValue(workspace.threshold.value() + 0.5)
    else:
        workspace.total_gas_lod.setValue(0.25)
    qapp.processEvents()
    assert workspace._method_comparisons == ()
    assert workspace._comparison_dialog is None
    workspace.close()


def test_mixture_mode_disables_comparison_action(qapp) -> None:
    workspace = _workspace()
    mode_index = workspace.report_mode.findData("mixture_text")
    assert mode_index >= 0
    workspace.report_mode.setCurrentIndex(mode_index)
    workspace.refresh()
    qapp.processEvents()
    assert not workspace.compare_methods_button.isEnabled()
    assert workspace._method_comparisons == ()
    workspace.close()


def test_comparison_service_rejects_unrelated_depth_axis(qapp) -> None:
    workspace = _workspace()
    assert workspace.report is not None
    standard = workspace.report
    incompatible = replace(
        standard, report_profile="opus", depth_axis_id="unrelated-axis",
    )
    with pytest.raises(ValueError, match="оси глубины"):
        compare_standard_opus_reports(standard, incompatible)
    workspace.close()
