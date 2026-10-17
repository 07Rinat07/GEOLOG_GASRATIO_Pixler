"""Opt-in spreadsheet evidence reuses the same localized comparison as HTML/PDF."""

from __future__ import annotations

from dataclasses import replace
from html import escape

import numpy as np
import pytest
from openpyxl import load_workbook  # type: ignore[import-untyped]

from geoworkbench.data.hydrocarbon_interpretation_export import (
    export_hydrocarbon_interpretation_xlsx,
)
from geoworkbench.data import hydrocarbon_interpretation_export_readable as readable
from geoworkbench.services.fluid_phase_contract import FluidPhaseContract
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
)
from geoworkbench.services.interpretation_method_comparison import (
    MethodComparisonInterval,
    MethodComparisonStatus,
)
from geoworkbench.services.interpretation_method_comparison_html import (
    method_comparison_html,
    method_comparison_table,
)
from geoworkbench.services.localization import AppLanguage
from test_readable_interpretation_export import _session_with_zero_heavy_components


def _comparison() -> MethodComparisonInterval:
    return MethodComparisonInterval(
        standard_bounds=(1018.0, 1022.0),
        opus_bounds=(1018.0, 1022.0),
        status=MethodComparisonStatus.AGREEMENT,
        reason_code="bounded_phase_agreement",
        overlap_depth=4.0,
        standard_overlap_fraction=0.8,
        opus_overlap_fraction=0.5,
        standard_phase=FluidPhaseContract.GAS,
        opus_phase=FluidPhaseContract.GAS,
        standard_wetness_robust_z=3.2,
        standard_pixler_c1_c2=17.0,
        opus_class_code=3,
        opus_support_fraction=0.625,
        opus_valid_rows=8,
    )


@pytest.mark.parametrize(
    ("language", "sheet_name"),
    (
        (AppLanguage.RU, "Сравнение методов"),
        (AppLanguage.KK, "Әдістерді салыстыру"),
        (AppLanguage.EN, "Method comparison"),
    ),
)
def test_comparison_worksheet_matches_canonical_html_evidence(
    tmp_path, language: AppLanguage, sheet_name: str,
) -> None:
    session = _session_with_zero_heavy_components()
    dataset = session.current_dataset
    assert dataset is not None
    depth = dataset.depth.copy()
    report = build_hydrocarbon_interpretation_report(session)
    original = replace(report)
    comparison = _comparison()
    projection = method_comparison_table((comparison,), language, depth_unit="m")
    html = method_comparison_html((comparison,), language, depth_unit="m")

    target = export_hydrocarbon_interpretation_xlsx(
        report, dataset, tmp_path / "comparison.xlsx", language=language,
        method_comparisons=(comparison,),
    )
    workbook = load_workbook(target, read_only=False, data_only=False)
    try:
        assert sheet_name in workbook.sheetnames
        sheet = workbook[sheet_name]
        assert tuple(sheet.cell(1, i).value for i in range(1, 6)) == projection.headings
        assert tuple(sheet.cell(2, i).value for i in range(1, 6)) == projection.rows[0].cells
        assert sheet["F2"].value == "bounded_phase_agreement"
        assert sheet["G2"].value == 1
        assert sheet.column_dimensions["F"].hidden
        assert sheet.column_dimensions["G"].hidden
        assert sheet["A2"].value == "1018.00–1022.00 m"
        assert "62.5%" in str(sheet["E2"].value)
        assert sheet["A1"].value in html
        assert escape(projection.rows[0].cells[3]) in html
        assert escape(projection.rows[0].cells[4]) in html
        assert not any("Method comparison" == name for name in workbook.sheetnames if language is not AppLanguage.EN)
    finally:
        workbook.close()
    np.testing.assert_array_equal(dataset.depth, depth)
    assert report == original


def test_default_workbook_has_no_unrequested_comparison_sheet(tmp_path) -> None:
    session = _session_with_zero_heavy_components()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)
    target = export_hydrocarbon_interpretation_xlsx(
        report, dataset, tmp_path / "normal.xlsx",
    )
    book = load_workbook(target, read_only=True, data_only=True)
    try:
        assert not any("Сравнение методов" == name for name in book.sheetnames)
        assert not any("Method comparison" == name for name in book.sheetnames)
    finally:
        book.close()


def test_untrusted_reason_code_is_never_an_excel_formula(tmp_path) -> None:
    session = _session_with_zero_heavy_components()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)
    unsafe = replace(
        _comparison(), reason_code="=SUM(1,2)",
        standard_wetness_robust_z=None,
        standard_pixler_c1_c2=None,
        opus_support_fraction=None,
    )
    target = export_hydrocarbon_interpretation_xlsx(
        report, dataset, tmp_path / "unsafe.xlsx",
        method_comparisons=(unsafe,),
    )
    book = load_workbook(target, read_only=False, data_only=False)
    try:
        sheet = book["Сравнение методов"]
        assert sheet["F2"].data_type == "s"
        assert sheet["F2"].value == "'=SUM(1,2)"
        assert "—" in str(sheet["E2"].value)
        assert sheet["G2"].value == 1
    finally:
        book.close()


@pytest.mark.parametrize("with_comparison", (False, True))
def test_public_export_api_forwards_only_requested_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path, with_comparison: bool,
) -> None:
    calls: list[dict[str, object]] = []

    def legacy_export(*args: object, **kwargs: object):
        calls.append(kwargs)
        return tmp_path / "stub.xlsx"

    monkeypatch.setattr(
        readable, "export_readable_hydrocarbon_interpretation_xlsx", legacy_export,
    )
    comparison = (_comparison(),) if with_comparison else ()
    target = export_hydrocarbon_interpretation_xlsx(
        object(), object(), tmp_path / "stub.xlsx",  # type: ignore[arg-type]
        method_comparisons=comparison,
    )
    assert target.name == "stub.xlsx"
    assert calls[0].get("method_comparisons", ()) == comparison
    assert ("method_comparisons" in calls[0]) is with_comparison
