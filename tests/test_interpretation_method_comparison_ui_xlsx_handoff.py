"""Opt-in Qt comparison handoff to the existing readable Excel export."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from openpyxl import load_workbook  # type: ignore[import-untyped]

from geoworkbench.data import hydrocarbon_interpretation_export_readable as readable
from geoworkbench.services.interpretation_method_comparison_html import (
    method_comparison_table,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import interpretation_report_workspace_legacy as legacy
from test_interpretation_method_comparison_chart_html import _comparison
from test_interpretation_method_comparison_explicit_ui import _workspace


@pytest.mark.parametrize(
    ("language", "sheet_name"),
    (
        (AppLanguage.RU, "Сравнение методов"),
        (AppLanguage.KK, "Әдістерді салыстыру"),
        (AppLanguage.EN, "Method comparison"),
    ),
)
def test_explicit_comparison_included_in_real_readable_xlsx(
    tmp_path: Path,
    qapp,
    monkeypatch: pytest.MonkeyPatch,
    language: AppLanguage,
    sheet_name: str,
) -> None:
    workspace = _workspace(language)
    assert workspace.report is not None

    def opus(session, **kwargs):
        del session, kwargs
        assert workspace.report is not None
        return replace(workspace.report, report_profile="opus")

    monkeypatch.setattr(legacy, "build_opus_interpretation_report", opus)
    monkeypatch.setattr(
        legacy, "compare_standard_opus_reports",
        lambda standard, companion: (_comparison(),),
    )
    target = tmp_path / "explicit.xlsx"
    monkeypatch.setattr(workspace, "_choose_target", lambda suffix, file_filter: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda path: None)
    workspace.compare_methods_button.click()
    qapp.processEvents()

    workspace._export_xlsx()
    assert target.exists()
    expected = method_comparison_table(
        (_comparison(),), language, depth_unit=workspace.report.depth_unit,
    )
    workbook = load_workbook(target, read_only=False, data_only=False)
    try:
        assert sheet_name in workbook.sheetnames
        sheet = workbook[sheet_name]
        assert tuple(sheet.cell(1, i).value for i in range(1, 6)) == expected.headings
        assert tuple(sheet.cell(2, i).value for i in range(1, 6)) == expected.rows[0].cells
        assert sheet["F2"].value == expected.rows[0].reason_code
        assert sheet["G2"].value == expected.rows[0].reason_version
        assert sheet.column_dimensions["F"].hidden
        assert sheet.column_dimensions["G"].hidden
    finally:
        workbook.close()
    assert workspace._method_comparisons == (_comparison(),)
    workspace.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_default_ui_workbook_keeps_legacy_export_arguments(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: AppLanguage,
) -> None:
    workspace = _workspace(language)
    target = tmp_path / "plain.xlsx"
    calls: list[dict[str, object]] = []

    def capture(report, dataset, target, **kwargs):
        del report, dataset
        calls.append(kwargs)
        return target

    monkeypatch.setattr(readable, "export_readable_hydrocarbon_interpretation_xlsx", capture)
    monkeypatch.setattr(workspace, "_choose_target", lambda suffix, file_filter: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda path: None)
    workspace._export_xlsx()
    assert len(calls) == 1
    assert "method_comparisons" not in calls[0]
    assert calls[0]["language"] is language
    assert calls[0]["identity"] is not None
    workspace.close()


@pytest.mark.parametrize("change", ("report", "dataset", "threshold"))
def test_stale_pair_never_reaches_xlsx_export(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    workspace = _workspace()
    assert workspace.report is not None

    def opus(session, **kwargs):
        del session, kwargs
        assert workspace.report is not None
        return replace(workspace.report, report_profile="opus")

    monkeypatch.setattr(legacy, "build_opus_interpretation_report", opus)
    monkeypatch.setattr(
        legacy, "compare_standard_opus_reports",
        lambda standard, companion: (_comparison(),),
    )
    workspace.compare_methods_button.click()
    qapp.processEvents()
    assert workspace._method_comparisons

    if change == "report":
        workspace.report = replace(workspace.report, generated_at="new-revision")
    elif change == "dataset":
        dataset = workspace.controller.session.current_dataset
        assert dataset is not None
        dataset.dataset_id = "new-source-id"
    else:
        workspace.threshold.blockSignals(True)
        workspace.threshold.setValue(workspace.threshold.value() + 0.5)
        workspace.threshold.blockSignals(False)

    target = tmp_path / "stale.xlsx"
    calls: list[dict[str, object]] = []

    def capture(report, dataset, target, **kwargs):
        del report, dataset
        calls.append(kwargs)
        return target

    monkeypatch.setattr(readable, "export_readable_hydrocarbon_interpretation_xlsx", capture)
    monkeypatch.setattr(workspace, "_choose_target", lambda suffix, file_filter: target)
    monkeypatch.setattr(workspace, "_show_export_success", lambda path: None)
    workspace._export_xlsx()
    assert len(calls) == 1
    assert "method_comparisons" not in calls[0]
    assert workspace._method_comparisons == ()
    assert workspace._comparison_source_key is None
    workspace.close()
