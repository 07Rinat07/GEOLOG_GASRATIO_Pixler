from __future__ import annotations

import csv
import math
from pathlib import Path

from openpyxl import Workbook  # type: ignore[import-untyped]
from openpyxl.styles import Alignment, Font, PatternFill  # type: ignore[import-untyped]

from geoworkbench.calculations.interval_statistics import CurveIntervalStatistics


STATISTICS_COLUMNS = (
    "Parameter",
    "Unit",
    "Valid points",
    "Coverage, %",
    "Minimum",
    "Maximum",
    "Mean",
)


def statistics_rows(
    statistics: tuple[CurveIntervalStatistics, ...],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            item.mnemonic,
            item.unit or "",
            item.valid_count,
            item.coverage_percent,
            _finite_or_none(item.minimum),
            _finite_or_none(item.maximum),
            _finite_or_none(item.mean),
        )
        for item in statistics
    )


def statistics_tsv(
    statistics: tuple[CurveIntervalStatistics, ...],
    *,
    interval_label: str,
    dataset_name: str,
) -> str:
    lines = [f"Dataset\t{dataset_name}", f"Interval\t{interval_label}"]
    lines.append("\t".join(STATISTICS_COLUMNS))
    for row in statistics_rows(statistics):
        lines.append("\t".join(_text(value) for value in row))
    return "\n".join(lines)


def export_interval_statistics_csv(
    path: str | Path,
    statistics: tuple[CurveIntervalStatistics, ...],
    *,
    interval_label: str,
    dataset_name: str,
) -> Path:
    target = Path(path)
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Dataset", dataset_name))
        writer.writerow(("Interval", interval_label))
        writer.writerow(())
        writer.writerow(STATISTICS_COLUMNS)
        writer.writerows(statistics_rows(statistics))
    return target


def export_interval_statistics_xlsx(
    path: str | Path,
    statistics: tuple[CurveIntervalStatistics, ...],
    *,
    interval_label: str,
    dataset_name: str,
) -> Path:
    target = Path(path)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Interval statistics"
    sheet.append(("Dataset", dataset_name))
    sheet.append(("Interval", interval_label))
    sheet.append(())
    sheet.append(STATISTICS_COLUMNS)
    for row in statistics_rows(statistics):
        sheet.append(row)

    header_fill = PatternFill("solid", fgColor="DCE6F1")
    for cell in sheet[4]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
    widths = (24, 14, 14, 14, 16, 16, 16)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width
    for row in sheet.iter_rows(min_row=5, min_col=4, max_col=7):
        for cell in row:
            cell.number_format = "0.########"
    sheet.freeze_panes = "A5"
    sheet.auto_filter.ref = f"A4:G{max(4, sheet.max_row)}"
    workbook.save(target)
    return target


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def _finite_or_none(value: float) -> float | None:
    return value if math.isfinite(value) else None
