from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.interpretation_calculation_controller import (
    NormalizedGasCalculationMode,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.report_visual_system import REPORT_BRAND_WORDMARK
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
    hydrocarbon_interpretation_html,
)
from geoworkbench.services.localization import AppLanguage


def _add_curve(
    dataset: Dataset,
    mnemonic: str,
    values: np.ndarray,
    unit: str,
    provenance: str = "source:test",
) -> None:
    dataset.curves[mnemonic] = CurveData(
        CurveMetadata(
            mnemonic,
            mnemonic,
            mnemonic,
            unit,
            mnemonic,
            dataset.dataset_id,
            provenance,
        ),
        np.asarray(values, dtype=np.float64),
    )


def _session_with_zero_heavy_components() -> ProjectSession:
    depth = np.arange(1_000.0, 1_040.0)
    dataset = Dataset(
        "readable-interpretation",
        "Readable interpretation",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    normalized = np.ones(depth.shape)
    normalized[20:23] = (10.0, 12.0, 11.0)
    raw_total = np.full(depth.shape, 0.2)
    raw_total[20:23] = (3.0, 4.0, 5.0)
    _add_curve(
        dataset,
        "TG_NORM_CALC",
        normalized,
        "normalized gas units",
        "calculation:test",
    )
    _add_curve(dataset, "TG_CALC", raw_total, "%abs")
    _add_curve(dataset, "C1", np.full(depth.shape, 10.0), "%")
    for mnemonic in ("C2", "C3", "C4", "C5"):
        _add_curve(dataset, mnemonic, np.zeros(depth.shape), "%")
    _add_curve(
        dataset,
        "DEXP",
        np.linspace(0.7, 1.1, depth.size),
        "dimensionless",
    )

    session = ProjectSession()
    session.add_dataset(dataset, "Well readable")
    session.dirty = False
    return session


def test_pdf_html_replaces_ambiguous_zero_wetness_with_explicit_gas_readings() -> None:
    from geoworkbench.services.hydrocarbon_interpretation_gas_html import (
        inject_interval_gas_statistics_html,
    )

    session = _session_with_zero_heavy_components()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(
        session,
        threshold=3.0,
        normalized_gas_mode=NormalizedGasCalculationMode.LOCAL,
    )

    html = inject_interval_gas_statistics_html(
        hydrocarbon_interpretation_html(report, AppLanguage.RU),
        report,
        dataset,
        AppLanguage.RU,
    )

    assert report.candidates
    assert "Исходный общий газ" in html
    assert "Нормализованный газ" in html
    assert "В интервале C2-C5 не зарегистрированы выше нуля" in html
    assert "Абсолютный газ: мин / среднее / макс" in html
    assert "Точек выше порога" not in html
    assert "фон 0.00000" not in html
    assert "Относительная доля C2–C5: интервал 0.00000%" not in html


def test_readable_xlsx_keeps_interpretation_and_gas_statistics_on_main_sheet(
    tmp_path,
) -> None:
    from openpyxl import load_workbook  # type: ignore[import-untyped]

    from geoworkbench.data.hydrocarbon_interpretation_export_readable import (
        export_readable_hydrocarbon_interpretation_xlsx,
    )

    session = _session_with_zero_heavy_components()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(
        session,
        threshold=3.0,
        normalized_gas_mode=NormalizedGasCalculationMode.LOCAL,
    )
    target = tmp_path / "interpretation.xlsx"

    export_readable_hydrocarbon_interpretation_xlsx(report, dataset, target)

    workbook = load_workbook(target, data_only=False)
    try:
        assert workbook.sheetnames[:2] == ["Интерпретация УВ", "Методика"]
        assert "Candidate intervals" not in workbook.sheetnames
        assert workbook["Данные по глубине"].sheet_state == "hidden"
        sheet = workbook["Интерпретация УВ"]
        assert str(sheet["A1"].value).startswith("Сводная интерпретация")
        print_wordmark = "&B" + REPORT_BRAND_WORDMARK.replace("&", "&&") + "&B"
        assert sheet.oddHeader.left.text == print_wordmark
        assert sheet.oddFooter.left.text == print_wordmark
        metadata_values = {
            str(sheet.cell(row, column).value)
            for row in range(1, 9)
            for column in range(1, 6)
            if sheet.cell(row, column).value is not None
        }
        assert report.generated_at not in metadata_values
        assert "Сформирован" not in metadata_values
        headers = [sheet.cell(9, column).value for column in range(1, 24)]
        assert "Предварительная интерпретация" in headers
        assert "Мин исходного газа" in headers
        assert "Среднее исходного газа" in headers
        assert "Макс исходного газа" in headers
        assert "Абсолютный газ по компонентам: мин / среднее / макс" in headers
        assert "Точек выше порога" not in headers
        assert not any("Медиана" in str(value) for value in headers)
        assert not any("Фон" in str(value) for value in headers)
        assert sheet["F10"].value == "Перспективный УВ-интервал"
        assert isinstance(sheet["G10"].value, str) and sheet["G10"].value
        assert sheet["I10"].value == "Общий газ [%abs]"
        assert sheet["J10"].value == 3.0
        assert sheet["K10"].value == 4.0
        assert sheet["L10"].value == 5.0
        assert sheet["M10"].value == "Расчётный нормализованный общий газ [normalized gas units]"
        assert sheet["N10"].value == 10.0
        assert sheet["O10"].value == 11.0
        assert sheet["P10"].value == 12.0
        assert "C1" in str(sheet["R10"].value)
        assert "среднее" in str(sheet["R10"].value)
        assert "0 — реальное нулевое измерение" in str(sheet["A7"].value)
    finally:
        workbook.close()


def test_readable_xlsx_reports_determinate_progress(tmp_path) -> None:
    from geoworkbench.data.hydrocarbon_interpretation_export_readable import (
        export_readable_hydrocarbon_interpretation_xlsx,
    )

    session = _session_with_zero_heavy_components()
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(
        session,
        threshold=3.0,
        normalized_gas_mode=NormalizedGasCalculationMode.LOCAL,
    )
    updates: list[tuple[str, int, int]] = []

    export_readable_hydrocarbon_interpretation_xlsx(
        report,
        dataset,
        tmp_path / "progress.xlsx",
        progress=lambda stage, current, total: updates.append((stage, current, total)),
    )

    assert updates[0] == ("Подготовка структуры Excel", 0, 100)
    assert any("Запись данных по глубине" in stage for stage, _current, _total in updates)
    assert updates[-1] == ("Excel-отчёт готов", 100, 100)
    assert [current for _stage, current, _total in updates] == sorted(
        current for _stage, current, _total in updates
    )


def test_raw_primary_gas_is_not_mislabelled_as_normalized_in_reports(tmp_path) -> None:
    from openpyxl import load_workbook  # type: ignore[import-untyped]

    from geoworkbench.data.hydrocarbon_interpretation_export_readable import (
        export_readable_hydrocarbon_interpretation_xlsx,
    )
    from geoworkbench.services.interval_gas_statistics import (
        CandidateIntervalGasStatistics,
        IntervalCurveStatistics,
        interval_gas_summary,
        is_normalized_primary_gas,
    )

    # TG_CALC is total gas derived from component readings, not drilling normalization.
    assert not is_normalized_primary_gas("TG_CALC")
    assert not is_normalized_primary_gas("OPUS_TG_PCT")
    assert is_normalized_primary_gas("TG_NORM_CALC")
    assert is_normalized_primary_gas("server:TG_NORM")

    raw = IntervalCurveStatistics("TG_CALC", "%abs", 3.0, 4.0, 4.0, 5.0, 0.1, 3, 3)
    normalized = IntervalCurveStatistics(
        "TG_NORM_CALC", "normalized gas units", 10.0, 11.0, 11.0, 12.0,
        1.0, 3, 3,
    )
    raw_summary = interval_gas_summary(CandidateIntervalGasStatistics(raw, None, (), None))
    normalized_summary = interval_gas_summary(
        CandidateIntervalGasStatistics(normalized, None, (), None)
    )
    assert "Основная газовая кривая Общий газ" in raw_summary
    assert "Нормализованный газ" not in raw_summary
    assert "Нормализованный газ" in normalized_summary

    session = _session_with_zero_heavy_components()
    dataset = session.current_dataset
    assert dataset is not None
    # Simulate the user's LAS which has TG_CALC but no normalized total.
    dataset.curves.pop("TG_NORM_CALC")
    report = build_hydrocarbon_interpretation_report(session, threshold=3.0)
    assert report.primary_mnemonic == "TG_CALC"
    target = tmp_path / "raw-gas.xlsx"
    export_readable_hydrocarbon_interpretation_xlsx(report, dataset, target)
    book = load_workbook(target)
    try:
        assert book["Интерпретация УВ"]["M8"].value == "Основная газовая кривая"
    finally:
        book.close()
