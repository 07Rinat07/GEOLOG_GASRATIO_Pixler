from __future__ import annotations

import hashlib

import pytest

from geoworkbench.data.late_analysis_adapter import (
    LateAnalysisImportError,
    load_late_analysis_source,
)
from geoworkbench.domain.analysis_update import AnalysisField
from geoworkbench.services.well_analysis_update import AnalysisSourceSample


def _values(sample: AnalysisSourceSample) -> dict[AnalysisField, object]:
    return {item.field: item.value for item in sample.values}


def test_load_late_analysis_csv_supports_aliases_and_comma_decimals(tmp_path) -> None:
    source = tmp_path / "late.csv"
    source.write_text(
        "Глубина от;Глубина до;ID образца;Кальцит %;Доломит %;Заключение\n"
        "1000,0;1001,0;s-1;35,5;12,0;oil show\n"
        "1001,0;1002,0;s-2;;8,5;\n",
        encoding="utf-8",
    )

    result = load_late_analysis_source(source)

    assert result.source_name == "late.csv"
    assert result.source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result.detected_fields == (
        AnalysisField.CALCITE_PERCENT,
        AnalysisField.DOLOMITE_PERCENT,
        AnalysisField.ANALYSIS_INTERPRETATION,
    )
    assert len(result.source_samples) == 2

    first = result.source_samples[0]
    assert (first.top_depth, first.bottom_depth, first.target_sample_id) == (
        1000.0,
        1001.0,
        "s-1",
    )
    assert _values(first) == {
        AnalysisField.CALCITE_PERCENT: 35.5,
        AnalysisField.DOLOMITE_PERCENT: 12.0,
        AnalysisField.ANALYSIS_INTERPRETATION: "oil show",
    }

    second_values = _values(result.source_samples[1])
    assert second_values[AnalysisField.CALCITE_PERCENT] is None
    assert second_values[AnalysisField.DOLOMITE_PERCENT] == 8.5
    assert second_values[AnalysisField.ANALYSIS_INTERPRETATION] is None


def test_load_late_analysis_csv_falls_back_to_cp1251(tmp_path) -> None:
    source = tmp_path / "late.txt"
    source.write_bytes(
        (
            "От;До;Кальцит;Интерпретация\n"
            "1500;1501;22,5;нефтепроявление\n"
        ).encode("cp1251")
    )

    result = load_late_analysis_source(source)

    assert len(result.source_samples) == 1
    assert _values(result.source_samples[0]) == {
        AnalysisField.CALCITE_PERCENT: 22.5,
        AnalysisField.ANALYSIS_INTERPRETATION: "нефтепроявление",
    }


def test_load_late_analysis_excel_reads_first_sheet(tmp_path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    source = tmp_path / "late.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Analyses"
    sheet.append(["top_depth", "bottom_depth", "sample_id", "lba_group", "lba_color"])
    sheet.append([2000.0, 2001.0, "s-10", 2, "yellow"])
    workbook.save(source)
    workbook.close()

    result = load_late_analysis_source(source)

    sample = result.source_samples[0]
    assert sample.target_sample_id == "s-10"
    assert _values(sample) == {
        AnalysisField.LBA_GROUP: 2,
        AnalysisField.LBA_COLOR: "yellow",
    }


def test_load_late_analysis_rejects_missing_depth_column(tmp_path) -> None:
    source = tmp_path / "late.csv"
    source.write_text(
        "top_depth;calcite_percent\n1000;20\n",
        encoding="utf-8",
    )

    with pytest.raises(LateAnalysisImportError, match="нижняя глубина"):
        load_late_analysis_source(source)


def test_load_late_analysis_rejects_ambiguous_analysis_mapping(tmp_path) -> None:
    source = tmp_path / "late.csv"
    source.write_text(
        "from;to;calcite;calcite_percent\n1000;1001;20;21\n",
        encoding="utf-8",
    )

    with pytest.raises(LateAnalysisImportError, match="неоднозначно"):
        load_late_analysis_source(source)


def test_load_late_analysis_rejects_invalid_interval(tmp_path) -> None:
    source = tmp_path / "late.csv"
    source.write_text(
        "from;to;calcite\n1001;1000;20\n",
        encoding="utf-8",
    )

    with pytest.raises(LateAnalysisImportError, match="должна быть больше"):
        load_late_analysis_source(source)


def test_load_late_analysis_rejects_non_integer_lba_group(tmp_path) -> None:
    source = tmp_path / "late.csv"
    source.write_text(
        "from;to;lba_group\n1000;1001;1,5\n",
        encoding="utf-8",
    )

    with pytest.raises(LateAnalysisImportError, match="целое число"):
        load_late_analysis_source(source)


def test_load_late_analysis_rejects_unsupported_extension(tmp_path) -> None:
    source = tmp_path / "late.json"
    source.write_text("{}", encoding="utf-8")

    with pytest.raises(LateAnalysisImportError, match="Неподдерживаемый формат"):
        load_late_analysis_source(source)
