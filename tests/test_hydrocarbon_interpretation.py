from __future__ import annotations

import zipfile

import numpy as np
from openpyxl import load_workbook

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
    export_hydrocarbon_interpretation_docx,
    export_hydrocarbon_interpretation_xlsx,
)
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.interpretation_controller import InterpretationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.localization import AppLanguage


def _session() -> ProjectSession:
    depth = np.arange(1_000.0, 1_100.0)
    dataset = Dataset(
        "well-log",
        "Whole <well> log",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    normalized_gas = np.ones(depth.shape)
    normalized_gas[40:43] = (80.0, 120.0, 90.0)
    for mnemonic, values, unit in (
        ("C1_NORM", normalized_gas, "normalized gas units"),
        ("WH", np.full(depth.shape, 12.0), "%"),
        ("C1_C2", np.full(depth.shape, 8.0), "ratio"),
        ("DEXP", np.full(depth.shape, 1.4), "dimensionless"),
    ):
        dataset.curves[mnemonic] = CurveData(
            CurveMetadata(
                mnemonic,
                mnemonic,
                mnemonic,
                unit,
                mnemonic,
                dataset.dataset_id,
                "calculation:test",
            ),
            values,
        )
    variation = np.resize(np.array([-0.30, -0.15, 0.0, 0.15, 0.30]), depth.shape)
    gas_components = {
        "C1": np.full(depth.shape, 90.0),
        "C2": 5.0 + variation,
        "C3": 3.0 + variation / 2.0,
        "IC4": np.full(depth.shape, 1.0),
        "NC4": np.full(depth.shape, 1.0),
        "IC5": np.full(depth.shape, 0.5),
        "NC5": np.full(depth.shape, 0.5),
    }
    for values, high_value in (
        (gas_components["C2"], 30.0),
        (gas_components["C3"], 20.0),
        (gas_components["IC4"], 5.0),
        (gas_components["NC4"], 5.0),
        (gas_components["IC5"], 2.5),
        (gas_components["NC5"], 2.5),
    ):
        values[40:43] = high_value
    for mnemonic, values in gas_components.items():
        dataset.curves[mnemonic] = CurveData(
            CurveMetadata(
                mnemonic,
                mnemonic,
                mnemonic,
                "%",
                mnemonic,
                dataset.dataset_id,
                "source:test",
            ),
            values,
        )
    session = ProjectSession()
    session.project.name = "=Project formula"
    session.add_dataset(dataset, "Well <A>")
    interpretation = InterpretationController(session)
    interpretation.add_interpretation("Geologist")
    interpretation.add_interval(
        1_039.5,
        1_043.5,
        "hydrocarbon show",
        "+Confirmed",
        comment="Check DST",
    )
    return session


def test_report_detects_relative_anomaly_and_keeps_manual_intervals_separate() -> None:
    report = build_hydrocarbon_interpretation_report(_session(), threshold=3.0)

    assert report.primary_mnemonic == "C1_NORM"
    assert len(report.candidates) == 1
    candidate = report.candidates[0]
    assert candidate.top_depth <= 1_040.0
    assert candidate.bottom_depth >= 1_042.0
    assert candidate.sample_count == 3
    assert candidate.anomaly_strength == "high"
    assert candidate.fluid_hypothesis == "probable_liquid_hydrocarbons"
    assert candidate.wetness_robust_z is not None
    assert candidate.wetness_robust_z > 2.0
    assert ("WH", 12.0) in candidate.metrics
    assert any("context medians: WH=12" in evidence for evidence in candidate.evidence)
    assert len(report.manual_intervals) == 1
    assert report.manual_intervals[0].label == "+Confirmed"
    assert any("не заключение" in warning for warning in report.warnings)

    html = hydrocarbon_interpretation_html(report, AppLanguage.RU)
    assert "background: #ffffff" in html
    assert "td { background: #ffffff; }" in html
    assert "Well &lt;A&gt;" in html
    assert "Кандидатные интервалы" in html
    assert "вероятные жидкие УВ" in html
    assert "Check DST" in html


def test_report_exports_openable_xlsx_and_docx(tmp_path) -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)
    xlsx_path = export_hydrocarbon_interpretation_xlsx(
        report,
        dataset,
        tmp_path / "interpretation.xlsx",
    )
    docx_path = export_hydrocarbon_interpretation_docx(
        report,
        tmp_path / "interpretation.docx",
    )

    workbook = load_workbook(xlsx_path, read_only=True, data_only=False)
    try:
        assert workbook.sheetnames == [
            "Summary",
            "Candidate intervals",
            "Manual intervals",
            "Methods",
            "Whole well",
        ]
        assert workbook["Summary"]["B1"].value == "'=Project formula"
        assert workbook["Candidate intervals"].max_row == 2
        assert (
            workbook["Candidate intervals"]["I2"].value
            == "probable_liquid_hydrocarbons"
        )
        assert workbook["Whole well"].max_row == dataset.depth.size + 1
    finally:
        workbook.close()
    with zipfile.ZipFile(docx_path) as package:
        assert package.testzip() is None
        document = package.read("word/document.xml").decode("utf-8")
        assert "Кандидатные интервалы" in document
        assert "жидкие УВ" in document
        assert "Check DST" in document


def test_report_falls_back_from_sparse_normalized_gas_to_total_gas() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.curves["C1_NORM"].values[:] = np.nan
    total_gas = np.ones(dataset.depth.shape)
    total_gas[60:63] = (70.0, 110.0, 80.0)
    dataset.curves["TG"] = CurveData(
        CurveMetadata(
            "TG",
            "TG",
            "TG",
            "%",
            "TG",
            dataset.dataset_id,
            "source:test",
        ),
        total_gas,
    )

    report = build_hydrocarbon_interpretation_report(session)

    assert report.primary_mnemonic == "TG"
    assert len(report.candidates) == 1


def test_report_can_interpret_probable_gas_without_claiming_final_fluid_type() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.curves["C1"].values[40:43] = 300.0
    for mnemonic in ("C2", "C3", "IC4", "NC4", "IC5", "NC5"):
        dataset.curves[mnemonic].values[40:43] = 0.1

    report = build_hydrocarbon_interpretation_report(session)

    assert report.candidates[0].fluid_hypothesis == "probable_gas"
    html = hydrocarbon_interpretation_html(report, AppLanguage.RU)
    assert "вероятный газ" in html
    assert "Категория «вода» по mud-gas не назначается" in html


def test_xlsx_export_rejects_mismatched_curve_lengths(tmp_path) -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)
    dataset.curves["WH"].values = dataset.curves["WH"].values[:-1]

    with np.testing.assert_raises_regex(
        HydrocarbonInterpretationExportError,
        "WH",
    ):
        export_hydrocarbon_interpretation_xlsx(
            report,
            dataset,
            tmp_path / "invalid.xlsx",
        )
