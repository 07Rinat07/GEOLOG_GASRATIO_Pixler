from openpyxl import load_workbook

from geoworkbench.calculations.interval_statistics import CurveIntervalStatistics
from geoworkbench.data.interval_statistics_export import (
    export_interval_statistics_csv,
    export_interval_statistics_xlsx,
    statistics_tsv,
)


def _statistics() -> tuple[CurveIntervalStatistics, ...]:
    return (CurveIntervalStatistics("ROP", "m/h", 3, 1.0, 5.0, 3.0, 4),)


def test_interval_statistics_tsv_is_excel_pasteable() -> None:
    text = statistics_tsv(
        _statistics(), interval_label="Depth: 100–103 m", dataset_name="Well A"
    )

    assert "Dataset\tWell A" in text
    assert "Parameter\tUnit\tValid points\tCoverage, %" in text
    assert "ROP\tm/h\t3\t75" in text


def test_interval_statistics_exports_csv_and_xlsx(tmp_path) -> None:
    csv_path = export_interval_statistics_csv(
        tmp_path / "statistics.csv",
        _statistics(),
        interval_label="Depth: 100–103 m",
        dataset_name="Well A",
    )
    xlsx_path = export_interval_statistics_xlsx(
        tmp_path / "statistics.xlsx",
        _statistics(),
        interval_label="Depth: 100–103 m",
        dataset_name="Well A",
    )

    assert "ROP,m/h,3,75.0,1.0,5.0,3.0" in csv_path.read_text(encoding="utf-8-sig")
    sheet = load_workbook(xlsx_path, data_only=True).active
    assert sheet["A1"].value == "Dataset"
    assert sheet["B1"].value == "Well A"
    assert sheet["A5"].value == "ROP"
    assert sheet["D5"].value == 75.0


def test_interval_statistics_exports_missing_values_as_empty_cells(tmp_path) -> None:
    missing = (CurveIntervalStatistics("EMPTY", "ppm", 0, float("nan"), float("nan"), float("nan"), 4),)

    text = statistics_tsv(
        missing, interval_label="Depth: 100–103 m", dataset_name="Well A"
    )
    xlsx_path = export_interval_statistics_xlsx(
        tmp_path / "missing.xlsx",
        missing,
        interval_label="Depth: 100–103 m",
        dataset_name="Well A",
    )

    assert "EMPTY\tppm\t0\t0\t\t\t" in text
    sheet = load_workbook(xlsx_path, data_only=True).active
    assert sheet["E5"].value is None
    assert sheet["F5"].value is None
    assert sheet["G5"].value is None
