from __future__ import annotations

import zipfile

import numpy as np
from openpyxl import load_workbook

from geoworkbench.data.hydrocarbon_interpretation_export import (
    export_hydrocarbon_interpretation_docx,
    export_hydrocarbon_interpretation_xlsx,
)
from geoworkbench.calculations.gas_ratio import (
    OPUS_SCREENING_PROFILE_ID,
    calculate_basic_ratios,
    calculate_opus_report_curves,
    calculate_opus_screening,
)
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.opus_interpretation import build_opus_interpretation_report
from geoworkbench.services.hydrocarbon_interpretation import hydrocarbon_interpretation_html
from geoworkbench.services.localization import AppLanguage


def test_opus_reproduces_published_c1_c5_worked_example() -> None:
    curves = calculate_opus_screening(
        np.array([98.315]),
        np.array([1.186]),
        np.array([0.206]),
        np.array([0.172]),
        np.array([0.120]),
    )

    assert OPUS_SCREENING_PROFILE_ID == "opus-lukyanov-c1-c5-relative-1987-1997"
    np.testing.assert_allclose(curves["OPUS3"].values, [60.18], rtol=2e-4)
    np.testing.assert_allclose(curves["OPUS4"].values, [6.2875], rtol=2e-3)
    np.testing.assert_allclose(curves["OPUS_K1_3"].values, [8.01], rtol=2e-3)
    # The source prints 0.09 after low-precision intermediate rounding.
    np.testing.assert_allclose(curves["OPUS_1_5"].values, [0.09], atol=0.01)


def test_opus_report_is_separate_and_does_not_double_count_c4_c5() -> None:
    source = {
        "C1": np.array([5.719]),
        "C2": np.array([0.069]),
        "C3": np.array([0.012]),
        "IC4": np.array([0.004]),
        "NC4": np.array([0.006]),
        "IC5": np.array([0.003]),
        "NC5": np.array([0.004]),
        "C4": np.array([99.0]),
        "C5": np.array([99.0]),
    }

    standard = calculate_basic_ratios(source)
    curves = calculate_opus_report_curves(source)

    assert not any(name.startswith("OPUS") for name in standard)
    assert {"OPUS3", "OPUS4", "OPUS_K1_3", "OPUS_1_5"} <= curves.keys()
    np.testing.assert_allclose(curves["OPUS3"].values, [60.1449474], rtol=1e-7)


def test_opus_preserves_invalid_rows_as_nan() -> None:
    curves = calculate_opus_screening(
        np.array([80.0, np.nan, 0.0]),
        np.array([10.0, 10.0, 0.0]),
        np.array([5.0, 5.0, 0.0]),
        np.array([3.0, 3.0, 0.0]),
        np.array([2.0, 2.0, 0.0]),
    )

    for result in curves.values():
        assert np.isfinite(result.values[0])
        assert np.isnan(result.values[1])
        assert np.isnan(result.values[2])


def test_opus_handles_full_5000_m_well_at_point_two_metre_step() -> None:
    depth = np.arange(0.0, 5000.0 + 0.2, 0.2)
    curves = calculate_opus_screening(
        np.full(depth.shape, 80.0),
        np.full(depth.shape, 10.0),
        np.full(depth.shape, 5.0),
        np.full(depth.shape, 3.0),
        np.full(depth.shape, 2.0),
    )

    assert depth.size == 25_001
    assert all(result.values.shape == depth.shape for result in curves.values())
    assert all(np.all(np.isfinite(result.values)) for result in curves.values())


def _opus_session(unit: str, scale: float) -> ProjectSession:
    depth = np.arange(0.0, 100.0, 1.0)
    dataset = Dataset(
        "opus-dataset",
        f"OPUS source {unit}",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    components = {
        "C1": np.full(depth.shape, 0.10 * scale),
        "C2": np.full(depth.shape, 0.02 * scale),
        "C3": np.full(depth.shape, 0.01 * scale),
        "C4": np.full(depth.shape, 0.005 * scale),
        "C5": np.full(depth.shape, 0.005 * scale),
    }
    for values in components.values():
        values[40:43] *= 10.0
    for mnemonic, values in components.items():
        dataset.upsert_curve(
            mnemonic,
            values,
            unit=unit,
            description=f"Source {mnemonic}",
            provenance="source:test",
        )
    session = ProjectSession()
    session.add_dataset(dataset, "OPUS well")
    return session


def test_separate_opus_controller_converts_ppm_to_percent_and_keeps_sources() -> None:
    session = _opus_session("ppm", 10_000.0)
    dataset = session.current_dataset
    assert dataset is not None
    source = dataset.curve_by_mnemonic("C1")
    assert source is not None
    original = source.values.copy()

    result = InterpretationCalculationController(session).calculate_opus_curves()

    assert not result.issues
    assert "OPUS_C1_PCT" in result.created
    np.testing.assert_allclose(dataset.curve_by_mnemonic("OPUS_C1_PCT").values, original * 1e-4)
    np.testing.assert_array_equal(source.values, original)
    assert source.metadata.unit == "ppm"
    assert dataset.curve_by_mnemonic("OPUS_C1_PCT").metadata.unit == "%vol"


def test_ppm_and_percent_inputs_produce_the_same_opus_report_curves() -> None:
    percent_session = _opus_session("%", 1.0)
    ppm_session = _opus_session("ppm", 10_000.0)
    percent_controller = InterpretationCalculationController(percent_session)
    ppm_controller = InterpretationCalculationController(ppm_session)

    percent_controller.calculate_opus_curves()
    ppm_controller.calculate_opus_curves()

    for mnemonic in ("OPUS_TG_PCT", "OPUS3", "OPUS4", "OPUS_K1_3", "OPUS_1_5"):
        percent_curve = percent_session.current_dataset.curve_by_mnemonic(mnemonic)
        ppm_curve = ppm_session.current_dataset.curve_by_mnemonic(mnemonic)
        np.testing.assert_allclose(percent_curve.values, ppm_curve.values, equal_nan=True)


def test_opus_report_is_marked_separate_and_uses_source_applicability_gates() -> None:
    session = _opus_session("%", 1.0)
    InterpretationCalculationController(session).calculate_opus_curves()

    report = build_opus_interpretation_report(session, threshold=3.0)

    assert report.report_profile == "opus"
    assert report.primary_mnemonic == "OPUS_TG_PCT"
    assert len(report.candidates) == 1
    assert any("OPUS interval means" in item for item in report.candidates[0].evidence)
    assert any("отдельный дополнительный отчёт" in warning for warning in report.warnings)
    assert "Дополнительный отчёт ОПУС" in hydrocarbon_interpretation_html(
        report, AppLanguage.RU
    )


def test_opus_xlsx_contains_every_depth_row_and_working_percent_curves(tmp_path) -> None:
    session = _opus_session("ppm", 10_000.0)
    dataset = session.current_dataset
    assert dataset is not None
    InterpretationCalculationController(session).calculate_opus_curves()
    report = build_opus_interpretation_report(session)

    path = export_hydrocarbon_interpretation_xlsx(report, dataset, tmp_path / "opus.xlsx")
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        assert workbook["Интерпретация УВ"]["A1"].value.startswith(
            "Дополнительный отчёт ОПУС"
        )
        depth_sheet = workbook["Данные по глубине"]
        assert depth_sheet.max_row == dataset.depth.size + 1
        headers = [cell.value for cell in next(depth_sheet.iter_rows(min_row=1, max_row=1))]
        assert any(str(value).startswith("OPUS_C1_PCT ") for value in headers)
        assert any(str(value).startswith("OPUS_P1 ") for value in headers)
        assert any(str(value).startswith("OPUS3 ") for value in headers)
    finally:
        workbook.close()
    docx_path = export_hydrocarbon_interpretation_docx(
        report, tmp_path / "opus.docx", dataset=dataset
    )
    with zipfile.ZipFile(docx_path) as package:
        document = package.read("word/document.xml").decode("utf-8")
        assert "Дополнительный отчёт ОПУС" in document
        assert "OPUS interval means" in document
