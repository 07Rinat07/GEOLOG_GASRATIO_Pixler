from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_report_definition_resolves_semantic_requests_into_coverage() -> None:
    source = _source("src/geoworkbench/services/report_definition.py")

    assert "channel_mnemonics" in source
    assert "unavailable_channel_mnemonics" in source
    assert "analyze_dataset_coverage(" in source
    assert "coverage=coverage" in source


def test_tabular_export_keeps_zero_blank_and_unavailable_distinct() -> None:
    source = _source("src/geoworkbench/data/selection_export.py")

    assert 'UNAVAILABLE_CELL = "#N/A"' in source
    assert "None if not np.isfinite(curve.values[index])" in source
    assert "format_decimal_number(float(value))" in source
    assert "unavailable_mnemonics=report.unavailable_channel_mnemonics" in _source(
        "src/geoworkbench/project/dataset_export_controller.py"
    )


def test_report_passport_signs_coverage_snapshot() -> None:
    source = _source("src/geoworkbench/services/report_passport.py")

    assert "class ReportCoverageSnapshot" in source
    assert "coverage: tuple[ReportCoverageSnapshot, ...]" in source
    assert "unavailable_channel_coverage" in source
    assert "coverage=coverage" in source


def test_json_and_parquet_exports_publish_coverage_metadata() -> None:
    assert '"coverage": analyze_curve_coverage(' in _source(
        "src/geoworkbench/data/dataset_json_export.py"
    )
    assert '"coverage": coverage.payload()' in _source(
        "src/geoworkbench/data/dataset_parquet_export.py"
    )
