from __future__ import annotations

from dataclasses import replace
import zipfile

import fitz
import numpy as np
from openpyxl import load_workbook

from geoworkbench.data.hydrocarbon_interpretation_export import (
    HydrocarbonInterpretationExportError,
    export_hydrocarbon_interpretation_docx,
    export_hydrocarbon_interpretation_xlsx,
)
from geoworkbench.domain.gas_context_events import (
    GasContextEvent,
    GasContextEventType,
    InterpretationImpact,
)
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    CuttingsComponent,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.printing.hydrocarbon_interpretation_geology import (
    interpretation_geology_snapshot,
)
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.project.interpretation_controller import InterpretationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
    candidate_evidence_summary,
    fluid_hypothesis_basis,
    fluid_hypothesis_label,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.hydrocarbon_interpretation_gas_html import (
    inject_interval_gas_statistics_html,
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
    assert candidate.fluid_hypothesis == "heavy_or_residual_oil"
    assert candidate.wetness_robust_z is not None
    assert candidate.wetness_robust_z > 2.0
    assert ("WH", 12.0) in candidate.metrics
    assert any("context means: WH=12" in evidence for evidence in candidate.evidence)
    assert len(report.manual_intervals) == 1
    assert report.manual_intervals[0].label == "+Confirmed"
    assert any("не заключение" in warning for warning in report.warnings)
    assert report.report_profile == "standard"
    assert not any(method.method.startswith("OPUS") for method in report.methods)

    html = hydrocarbon_interpretation_html(report, AppLanguage.RU)
    assert "background: #ffffff" in html
    assert "td { background: #ffffff; }" in html
    assert "Well &lt;A&gt;" in html
    assert "Перспективные интервалы" in html
    assert "Кандидатные интервалы" not in html
    assert report.generated_at not in html
    assert "Сформирован" not in html

    kk_html = hydrocarbon_interpretation_html(report, AppLanguage.KK)
    assert "Көмірсутек көріністерінің перспективалы аралықтары" in kk_html
    assert "Көмірсутек көріністерінің кандидат аралықтары" not in kk_html

    en_html = hydrocarbon_interpretation_html(report, AppLanguage.EN)
    assert "Prospective hydrocarbon-show intervals" in en_html
    assert "Candidate hydrocarbon-show intervals" not in en_html
    assert "page-break-before: always" in html
    assert "жидкая УВ-фаза" in html
    assert "Check DST" in html


def test_report_replaces_legacy_gas_vendor_codes_with_readable_names() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None

    vendor_codes = {
        "C1": "S1601",
        "C2": "S1602",
        "C3": "S1603",
        "IC4": "S1626",
        "IC5": "S1627",
    }
    for canonical, vendor_code in vendor_codes.items():
        curve = dataset.curve_by_mnemonic(canonical)
        assert curve is not None
        metadata = curve.metadata
        curve.metadata = CurveMetadata(
            curve_id=metadata.curve_id,
            original_mnemonic=vendor_code,
            canonical_mnemonic=canonical,
            unit=metadata.unit,
            description=metadata.description,
            source_dataset_id=metadata.source_dataset_id,
            provenance=metadata.provenance,
            semantic=metadata.semantic,
        )

    report = build_hydrocarbon_interpretation_report(session)
    html = hydrocarbon_interpretation_html(report, AppLanguage.RU)
    html = inject_interval_gas_statistics_html(
        html,
        report,
        dataset,
        AppLanguage.RU,
    )

    assert "Содержание метана (C1)" in html
    assert "Этан (C2)" in html
    assert "Пропан (C3)" in html
    assert "Изобутан (IC4)" in html
    assert "Изопентан (IC5)" in html
    for vendor_code in vendor_codes.values():
        assert vendor_code not in html


def test_printable_evidence_humanizes_normalized_gas_curve_name() -> None:
    report = build_hydrocarbon_interpretation_report(_session())
    candidate = report.candidates[0]
    readable = candidate_evidence_summary(
        replace(
            candidate,
            evidence=(
                "normalized-gas source=local-calculation; curve=TG_NORM_CALC",
                "TG_NORM_CALC: max robust z = 4.02 (threshold 3.00)",
            ),
        ),
        AppLanguage.RU,
    )

    assert "Нормализованный газ: источник — локальный расчёт" in readable
    assert "Расчётный нормализованный общий газ" in readable
    assert "(TG_NORM_CALC)" not in readable
    assert "source=local-calculation" not in readable
    assert "curve=TG_NORM_CALC" not in readable


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
        dataset=dataset,
    )

    workbook = load_workbook(xlsx_path, read_only=True, data_only=False)
    try:
        assert workbook.sheetnames == [
            "Интерпретация УВ",
            "Методика",
            "Данные по глубине",
            "Реквизиты",
            "_classification_audit",
        ]
        main = workbook["Интерпретация УВ"]
        assert main["B2"].value == "'=Project formula"
        assert main["A5"].value == "Перспективных УВ-интервалов"
        headers = [main.cell(9, column).value for column in range(1, 24)]
        assert "Абсолютный газ по компонентам: мин / среднее / макс" in headers
        assert "Точек выше порога" not in headers
        assert not any("Медиана" in str(value) for value in headers)
        assert not any("Фон" in str(value) for value in headers)
        assert main["F10"].value == "Подтвержден геологом"
        assert "Кандидат" not in str(main["F10"].value)
        assert "C1" in str(main["R10"].value)
        assert "IC4" in str(main["R10"].value)
        assert "NC5" in str(main["R10"].value)
        assert workbook["Данные по глубине"].max_row == dataset.depth.size + 1
    finally:
        workbook.close()
    with zipfile.ZipFile(docx_path) as package:
        assert package.testzip() is None
        document = package.read("word/document.xml").decode("utf-8")
        assert "Перспективные интервалы" in document
        assert "Кандидатные интервалы" not in document
        assert "жидкая УВ-фаза" in document
        assert "Абсолютный газ: мин / среднее / макс" in document
        assert "Точек выше порога" not in document
        assert "Медиана" not in document
        assert "Фон" not in document
        assert "IC4" in document and "NC5" in document
        assert "Check DST" in document
        assert report.generated_at not in document
        assert "Сформирован" not in document


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


def test_report_uses_server_normalized_gas_alias_and_discloses_its_origin() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    server_values = np.ones(dataset.depth.shape)
    server_values[65:68] = (75.0, 115.0, 85.0)
    dataset.curves["server-tg-norm"] = CurveData(
        CurveMetadata(
            "server-tg-norm",
            "NORMALIZED_TOTAL_GAS",
            "NORMALIZED_TOTAL_GAS",
            "normalized gas units",
            "Operator normalized total gas",
            dataset.dataset_id,
            "source:server",
        ),
        server_values,
    )

    report = build_hydrocarbon_interpretation_report(session)

    assert report.primary_mnemonic == "NORMALIZED_TOTAL_GAS"
    assert any(
        "NORMALIZED_TOTAL_GAS" in warning and "из файла/сервера" in warning
        for warning in report.warnings
    )
    assert len(report.candidates) == 1


def test_report_can_interpret_probable_gas_without_claiming_final_fluid_type() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    dataset.curves["C1"].values[40:43] = 300.0
    for mnemonic in ("C2", "C3", "IC4", "NC4", "IC5", "NC5"):
        dataset.curves[mnemonic].values[40:43] = 0.1

    report = build_hydrocarbon_interpretation_report(session)

    assert report.candidates[0].fluid_hypothesis == "very_light_dry_gas"
    assert any(
        "Категория «вода» по mud-gas не назначается" in warning
        for warning in report.warnings
    )
    html = hydrocarbon_interpretation_html(report, AppLanguage.RU)
    assert "газовая УВ-фаза" in html
    assert "Pixler: очень лёгкий метановый газ" in html
    assert "Категория «вода» по mud-gas не назначается" not in html


def test_sparse_heavy_components_use_integrated_interval_composition() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    for mnemonic in ("C2", "C3", "IC4", "NC4", "IC5", "NC5"):
        values = dataset.curve_by_mnemonic(mnemonic).values
        values[40:43] = (0.0, 0.0, 0.001)

    report = build_hydrocarbon_interpretation_report(session)

    candidate = report.candidates[0]
    assert candidate.interval_wetness is not None
    assert candidate.interval_wetness > 0.0
    html = hydrocarbon_interpretation_html(report, AppLanguage.RU)
    assert f"{candidate.interval_wetness:.5f}%" in html
    assert "Точек выше порога" not in html
    assert "Абсолютный газ: мин / среднее / макс" in html
    assert "фон 0.00000" not in html


def test_report_correlates_gas_interpretation_with_overlapping_lba() -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.cuttings.append(
        CuttingsSample(
            "lba-overlap",
            1_039.5,
            1_043.5,
            lba_group=4,
            lba_type_id="СБ",
            lba_intensity=4,
            lba_color="ОК — оранжево-коричневый",
        )
    )

    report = build_hydrocarbon_interpretation_report(session)

    candidate = report.candidates[0]
    assert candidate.gas_lba_correlation == "concordant"
    assert candidate.lba_assessments[0].standard.code == "СБ"
    html = hydrocarbon_interpretation_html(report, AppLanguage.RU)
    assert "ЛБА: группа 4" in html
    assert "признаки согласуются" in html


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


def test_confirmed_technological_gas_suppresses_geological_candidate_and_exports_context(
    tmp_path,
) -> None:
    session = _session()
    well = session.current_well
    dataset = session.current_dataset
    assert well is not None
    assert dataset is not None
    dataset.curves["TG"] = CurveData(
        CurveMetadata(
            "TG",
            "TG",
            "TG",
            "%",
            "Measured total gas",
            dataset.dataset_id,
            "source:test",
        ),
        np.full(dataset.depth.shape, 4.0),
    )
    well.gas_context_events.append(
        GasContextEvent(
            event_id="connection-1",
            event_type=GasContextEventType.CONNECTION_GAS,
            top_depth=1_039.0,
            bottom_depth=1_043.0,
            confirmed=True,
            reported_total_gas=4.25,
            reported_unit="%",
            comment="Connection gas QC",
        )
    )

    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    assert report.candidates == ()
    assert len(report.suppressed_candidates) == 1
    suppressed = report.suppressed_candidates[0]
    assert suppressed.top_depth <= 1_040.0
    assert suppressed.bottom_depth >= 1_042.0
    assert any(
        "gas-context: event_id=connection-1" in item
        and "impact=technological_gas" in item
        for item in suppressed.evidence
    )
    assert len(report.gas_context_events) == 1
    assert report.gas_context_events[0].event_id == "connection-1"
    assert len(report.gas_context_audit) == 1
    audit = report.gas_context_audit[0]
    assert audit.event_id == "connection-1"
    assert audit.measured_total_gas is not None
    assert audit.measured_total_gas.mnemonic == "TG"
    assert audit.measured_total_gas.minimum == 4.0
    assert audit.measured_total_gas.mean == 4.0
    assert audit.measured_total_gas.maximum == 4.0
    assert {item.mnemonic for item in audit.measured_components} >= {"C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5"}
    assert audit.manual_total_gas == 4.25
    assert audit.manual_unit == "%"
    assert audit.qc_delta_vs_measured_mean == 0.25
    assert audit.qc_delta_unit == "%vol"
    assert any("suppressed 1 automatic geological candidate" in item for item in report.warnings)

    html = hydrocarbon_interpretation_html(report, AppLanguage.RU)
    assert "Газовый контекст интерпретации" in html
    assert "CONN — Газ соединения" in html
    assert "ID события: connection-1" in html
    assert "Connection gas QC" in html
    assert "Измеренный TG" in html
    assert "Общий газ: min 4; mean 4; max 4 %" in html
    assert "QC Δ к среднему TG" in html
    assert "0.25 %vol" in html
    assert "Аудит подавленных автоматических кандидатов" not in html
    assert "gas-context: event_id=connection-1" not in html.split("<body", 1)[1]

    xlsx_path = export_hydrocarbon_interpretation_xlsx(
        report,
        dataset,
        tmp_path / "gas-context.xlsx",
    )
    workbook = load_workbook(xlsx_path, read_only=True, data_only=False)
    try:
        assert "Газовый контекст" in workbook.sheetnames
        context_sheet = workbook["Газовый контекст"]
        assert context_sheet["A2"].value == "CONN — Газ соединения"
        assert context_sheet["E2"].value == "Технологический газ"
        assert context_sheet["F2"].value == "Общий газ [%]"
        assert context_sheet["G2"].value == 4.0
        assert context_sheet["H2"].value == 4.0
        assert context_sheet["I2"].value == 4.0
        assert "Содержание метана:" in context_sheet["J2"].value
        assert context_sheet["K2"].value == 4.25
        assert context_sheet["L2"].value == "%"
        assert context_sheet["M2"].value == 0.25
        assert context_sheet["N2"].value == "%vol"
        audit_values = [
            cell.value
            for row in context_sheet.iter_rows()
            for cell in row
            if cell.value is not None
        ]
        assert "Подавленные автоматические кандидаты — аудит" not in audit_values
        assert not any(
            "gas-context: event_id=connection-1" in str(value)
            for value in audit_values
        )
    finally:
        workbook.close()

    docx_path = export_hydrocarbon_interpretation_docx(
        report,
        tmp_path / "gas-context.docx",
        dataset=dataset,
    )
    with zipfile.ZipFile(docx_path) as package:
        document = package.read("word/document.xml").decode("utf-8")
        assert "Газовый контекст интерпретации" in document
        assert "CONN — Газ соединения" in document
        assert "ID события: connection-1" in document
        assert "Технологический газ" in document
        assert "Измеренный TG" in document
        assert "Общий газ: min 4; mean 4; max 4 %" in document
        assert "0.25 %vol" in document
        assert "Аудит подавленных автоматических кандидатов" not in document
        assert "gas-context: event_id=connection-1" not in document


def test_negative_tvdss_gas_context_flows_through_standard_report_and_xlsx(
    tmp_path,
) -> None:
    source_session = _session()
    source_dataset = source_session.current_dataset
    assert source_dataset is not None
    dataset = Dataset(
        "negative-tvdss-log",
        "Negative TVDSS log",
        DatasetKind.GTI,
        DepthDomain.TVDSS,
        source_dataset.depth - 1_100.0,
    )
    for curve_id, curve in source_dataset.curves.items():
        dataset.curves[curve_id] = CurveData(
            replace(curve.metadata, source_dataset_id=dataset.dataset_id),
            curve.values.copy(),
        )

    session = ProjectSession()
    session.add_dataset(dataset, "TVDSS well")
    well = session.current_well
    assert well is not None
    well.gas_context_events.append(
        GasContextEvent(
            event_id="negative-connection",
            event_type=GasContextEventType.CONNECTION_GAS,
            top_depth=-61.0,
            bottom_depth=-57.0,
            depth_domain=DepthDomain.TVDSS,
            confirmed=True,
            comment="negative TVDSS context",
        )
    )

    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    assert report.candidates == ()
    assert len(report.suppressed_candidates) == 1
    assert report.gas_context_events[0].top_depth == -61.0
    assert report.gas_context_events[0].bottom_depth == -57.0

    xlsx_path = export_hydrocarbon_interpretation_xlsx(
        report,
        dataset,
        tmp_path / "negative-tvdss.xlsx",
    )
    workbook = load_workbook(xlsx_path, read_only=True, data_only=False)
    try:
        context_sheet = workbook["Газовый контекст"]
        assert context_sheet["B2"].value == -61.0
        assert context_sheet["C2"].value == -57.0
    finally:
        workbook.close()


def test_confirmed_technological_context_is_excluded_from_robust_background() -> None:
    session = _session()
    well = session.current_well
    dataset = session.current_dataset
    assert well is not None
    assert dataset is not None

    primary = dataset.curve_by_mnemonic("C1_NORM")
    assert primary is not None
    # Simulate a long technological-gas interval that would materially bias the
    # robust background if it were learned as formation gas.
    primary.values[25:75] = 5.0
    primary.values[40:43] = (80.0, 120.0, 90.0)

    baseline_without_context = build_hydrocarbon_interpretation_report(
        session,
        threshold=3.0,
    ).baseline_median
    assert baseline_without_context is not None

    well.gas_context_events.append(
        GasContextEvent(
            event_id="background-exclusion",
            event_type=GasContextEventType.CONNECTION_GAS,
            top_depth=1_025.0,
            bottom_depth=1_074.0,
            confirmed=True,
            depth_domain=dataset.depth_domain,
        )
    )
    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    assert report.baseline_median is not None
    assert report.baseline_median < baseline_without_context
    assert report.candidates == ()
    assert len(report.suppressed_candidates) == 1


def test_draft_technological_context_remains_in_robust_background() -> None:
    session = _session()
    well = session.current_well
    dataset = session.current_dataset
    assert well is not None
    assert dataset is not None

    baseline_without_context = build_hydrocarbon_interpretation_report(
        session,
        threshold=3.0,
    ).baseline_median
    assert baseline_without_context is not None

    well.gas_context_events.append(
        GasContextEvent(
            event_id="draft-background",
            event_type=GasContextEventType.TRIP_GAS,
            top_depth=1_040.0,
            bottom_depth=1_042.0,
            confirmed=False,
            depth_domain=dataset.depth_domain,
        )
    )
    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    assert report.baseline_median == baseline_without_context
    assert len(report.candidates) == 1


def test_confirmed_formation_context_keeps_candidate_and_adds_audit_evidence() -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.gas_context_events.append(
        GasContextEvent(
            event_id="formation-1",
            event_type=GasContextEventType.FORMATION_SHOW,
            top_depth=1_039.0,
            bottom_depth=1_043.0,
            impact=InterpretationImpact.FORMATION_GAS,
            confirmed=True,
            comment="Geologist confirmed formation gas",
        )
    )

    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    assert len(report.candidates) == 1
    assert any(
        "gas-context: event_id=formation-1" in item
        and "impact=formation_gas" in item
        for item in report.candidates[0].evidence
    )
    assert not any("suppressed" in item for item in report.warnings)


def test_draft_technological_context_does_not_change_candidate_classification() -> None:
    session = _session()
    well = session.current_well
    assert well is not None
    well.gas_context_events.append(
        GasContextEvent(
            event_id="draft-trip",
            event_type=GasContextEventType.TRIP_GAS,
            top_depth=1_039.0,
            bottom_depth=1_043.0,
            confirmed=False,
        )
    )

    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    assert len(report.candidates) == 1
    assert report.gas_context_events == ()



def test_unbound_legacy_context_is_not_applied_across_multiple_depth_domains() -> None:
    session = _session()
    well = session.current_well
    dataset = session.current_dataset
    assert well is not None
    assert dataset is not None

    well.datasets["tvd-dataset"] = Dataset(
        "tvd-dataset",
        "TVD companion",
        DatasetKind.GTI,
        DepthDomain.TVD,
        np.asarray(dataset.depth, dtype=np.float64),
    )
    well.gas_context_events.append(
        GasContextEvent(
            event_id="legacy-unbound-trip",
            event_type=GasContextEventType.TRIP_GAS,
            top_depth=1_039.0,
            bottom_depth=1_043.0,
            confirmed=True,
        )
    )

    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    assert len(report.candidates) == 1
    assert report.suppressed_candidates == ()
    assert report.gas_context_events == ()
    assert not any("suppressed" in item for item in report.warnings)


def test_hard_excluded_context_is_not_calculated_or_printed() -> None:
    session = _session()
    well = session.current_well
    dataset = session.current_dataset
    assert well is not None
    assert dataset is not None

    well.gas_context_events.append(
        GasContextEvent(
            event_id="hard-exclude-135-140",
            event_type=GasContextEventType.CHROMATOGRAPH_TEST_GAS,
            top_depth=1_039.0,
            bottom_depth=1_043.0,
            depth_domain=dataset.depth_domain,
            impact=InterpretationImpact.EXCLUDE_GEOLOGICAL,
            confirmed=True,
            comment="Do not use for geological calculation or interpretation",
        )
    )

    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    assert report.candidates == ()
    assert report.suppressed_candidates == ()
    assert all(item.event_id != "hard-exclude-135-140" for item in report.gas_context_events)
    assert all(item.event_id != "hard-exclude-135-140" for item in report.gas_context_audit)
    html = hydrocarbon_interpretation_html(report, AppLanguage.RU)
    assert "hard-exclude-135-140" not in html
    assert "Do not use for geological calculation or interpretation" not in html
    assert "exclude_geological" not in html


def test_narrow_hard_exclusion_keeps_separate_shows_on_both_sides() -> None:
    session = _session()
    well = session.current_well
    dataset = session.current_dataset
    assert well is not None and dataset is not None
    well.gas_context_events.append(GasContextEvent(
        event_id="excluded-peak-middle",
        event_type=GasContextEventType.CHROMATOGRAPH_TEST_GAS,
        top_depth=1_041.0,
        bottom_depth=1_041.0,
        depth_domain=dataset.depth_domain,
        impact=InterpretationImpact.EXCLUDE_GEOLOGICAL,
        confirmed=True,
    ))

    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    assert len(report.candidates) == 2
    assert report.candidates[0].bottom_depth < 1_041.0
    assert report.candidates[1].top_depth > 1_041.0
    assert sum(item.sample_count for item in report.candidates) == 2
    assert "excluded-peak-middle" not in hydrocarbon_interpretation_html(report, AppLanguage.RU)


def test_hard_exclusion_takes_precedence_over_overlapping_technological_audit() -> None:
    session = _session()
    well = session.current_well
    dataset = session.current_dataset
    assert well is not None and dataset is not None
    well.gas_context_events.extend((
        GasContextEvent(
            event_id="technical-overlap",
            event_type=GasContextEventType.CONNECTION_GAS,
            top_depth=1_039.0,
            bottom_depth=1_043.0,
            depth_domain=dataset.depth_domain,
            confirmed=True,
        ),
        GasContextEvent(
            event_id="hard-overlap",
            event_type=GasContextEventType.CHROMATOGRAPH_TEST_GAS,
            top_depth=1_040.5,
            bottom_depth=1_041.5,
            depth_domain=dataset.depth_domain,
            impact=InterpretationImpact.EXCLUDE_GEOLOGICAL,
            confirmed=True,
        ),
    ))

    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    assert report.candidates == ()
    assert report.suppressed_candidates == ()
    assert "hard-overlap" not in hydrocarbon_interpretation_html(report, AppLanguage.RU)



def test_conservative_liquid_hydrocarbon_wording_is_consistent_in_three_languages() -> None:
    report = build_hydrocarbon_interpretation_report(_session(), threshold=3.0)
    candidate = replace(
        report.candidates[0],
        fluid_hypothesis="probable_liquid_hydrocarbons",
        wetness_robust_z=1.5,
    )

    assert (
        fluid_hypothesis_label(candidate, AppLanguage.RU)
        == "жидкая УВ-фаза"
    )
    assert (
        fluid_hypothesis_label(candidate, AppLanguage.KK)
        == "сұйық КС фазасы"
    )
    assert (
        fluid_hypothesis_label(candidate, AppLanguage.EN)
        == "liquid hydrocarbon phase"
    )

    ru_basis = fluid_hypothesis_basis(candidate, AppLanguage.RU)
    kk_basis = fluid_hypothesis_basis(candidate, AppLanguage.KK)
    en_basis = fluid_hypothesis_basis(candidate, AppLanguage.EN)
    assert "не подтверждает нефть" in ru_basis
    assert "мұнайды жеке өзі растамайды" in kk_basis
    assert "does not confirm oil by itself" in en_basis
    assert "Конкретный нефтяной подтип автоматически не назначен" in ru_basis
    assert "Нақты мұнай қосалқы түрі автоматты түрде тағайындалмады" in kk_basis
    assert "No specific oil subtype is assigned automatically" in en_basis


def test_visible_report_humanizes_source_vendor_mnemonics() -> None:
    report = build_hydrocarbon_interpretation_report(_session(), threshold=3.0)
    dexp_method_index = next(
        index
        for index, method in enumerate(report.methods)
        if "d-exponent" in method.method.casefold()
    )
    methods = list(report.methods)
    methods[dexp_method_index] = replace(
        methods[dexp_method_index],
        available_mnemonics=("S224",),
    )
    humanized = replace(report, methods=tuple(methods), primary_mnemonic="S1600")

    html = hydrocarbon_interpretation_html(humanized, AppLanguage.RU)

    assert "D-exponent" in html
    assert "Общий газ" in html
    assert "S224" not in html
    assert "S1600" not in html


def test_weak_liquid_signature_in_report_is_downgraded_from_specific_oil() -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None

    # Keep the total-gas anomaly, but make interval C2-C5 enrichment only mildly
    # different from the well background while Haworth remains oil-like.
    dataset.curves["C1"].values[40:43] = 90.0
    dataset.curves["C2"].values[40:43] = 2.0
    dataset.curves["C3"].values[40:43] = 4.0
    dataset.curves["IC4"].values[40:43] = 1.5
    dataset.curves["NC4"].values[40:43] = 1.5
    dataset.curves["IC5"].values[40:43] = 1.0
    dataset.curves["NC5"].values[40:43] = 1.0

    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    candidate = report.candidates[0]
    assert candidate.interval_wetness is not None
    assert candidate.interval_balance is not None
    assert candidate.interval_character is not None
    assert candidate.interval_balance <= candidate.interval_wetness
    assert candidate.interval_character > 0.5
    assert candidate.wetness_robust_z is not None
    assert candidate.wetness_robust_z < 2.0
    assert candidate.fluid_hypothesis == "probable_liquid_hydrocarbons"


def test_interpretation_pdf_uses_immutable_current_well_geology_snapshot(
    qapp,
    tmp_path,
) -> None:
    session = _session()
    well = session.current_well
    dataset = session.current_dataset
    assert well is not None
    assert dataset is not None
    sample = CuttingsSample(
        "report-geology",
        1_020.0,
        1_030.0,
        [
            CuttingsComponent("sandstone", 70.0),
            CuttingsComponent("clay", 30.0),
        ],
        lba_group=2,
        lba_intensity=3,
        lba_color="yellow",
    )
    well.cuttings.append(sample)
    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)

    geology = interpretation_geology_snapshot(session)
    assert geology is not None
    assert geology.has_cuttings is True
    assert geology.has_lba is True
    assert geology.samples[0].components[0].percentage == 70.0
    assert geology.samples[0].lba_group == 2
    assert geology.samples[0].lba_type_id is None
    assert geology.samples[0].lba_intensity == 3

    sample.components[0].percentage = 5.0
    sample.lba_intensity = 5
    assert geology.samples[0].components[0].percentage == 70.0
    assert geology.samples[0].lba_intensity == 3

    target = tmp_path / "interpretation-geology.pdf"
    export_hydrocarbon_interpretation_pdf(
        report,
        target,
        dataset=dataset,
        include_chart=True,
        geology=geology,
    )

    with fitz.open(target) as document:
        text = "\n".join(page.get_text() for page in document)

    normalized_text = "".join(text.split())
    assert "Шламограмма" in normalized_text
    assert "ЛБА" in normalized_text
    assert "МБ" in normalized_text


def test_report_default_anomaly_threshold_is_four() -> None:
    from geoworkbench.services.hydrocarbon_interpretation import build_opus_interpretation_report

    assert build_hydrocarbon_interpretation_report(_session()).threshold == 4.0
    assert build_opus_interpretation_report(_session()).threshold == 4.0
    assert build_hydrocarbon_interpretation_report(_session(), threshold=3.0).threshold == 3.0


def test_unedited_project_placeholder_is_not_reported_as_a_real_project() -> None:
    session = _session()
    assert session.project.name == "Новый проект"
    report = build_hydrocarbon_interpretation_report(session)
    assert report.project_name == ""
    assert session.project.name == "Новый проект"  # no workspace mutation
    assert "Новый проект" not in hydrocarbon_interpretation_html(
        report, AppLanguage.RU,
    )

    # A real user-edited project name always takes precedence.
    session.project.name = "Площадь Максат — проект заказчика"
    edited = build_hydrocarbon_interpretation_report(session)
    assert edited.project_name == "Площадь Максат — проект заказчика"


def test_explicit_report_passport_may_override_an_unnamed_project() -> None:
    from dataclasses import replace as dc_replace
    from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
        default_interpretation_report_identity,
    )
    from geoworkbench.printing.report_document_control import resolved_report_identity

    session = _session()
    report = build_hydrocarbon_interpretation_report(session)
    supplied = dc_replace(
        default_interpretation_report_identity(report, AppLanguage.RU),
        project_name="М-1 — подтверждённые реквизиты",
    )
    assert resolved_report_identity(
        report, supplied, AppLanguage.RU,
    ).project_name == "М-1 — подтверждённые реквизиты"
