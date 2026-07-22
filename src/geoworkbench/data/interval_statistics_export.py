from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Mapping

from openpyxl import Workbook  # type: ignore[import-untyped]
from openpyxl.styles import Alignment, Font, PatternFill  # type: ignore[import-untyped]

from geoworkbench.calculations.interval_statistics import CurveIntervalStatistics
from geoworkbench.services.localization import AppLanguage, Localizer


def statistics_columns(language: AppLanguage = AppLanguage.EN) -> tuple[str, ...]:
    localizer = Localizer.create(language)
    return (
        localizer.text("statistics.parameter"),
        localizer.text("statistics.mnemonic"),
        localizer.text("statistics.unit"),
        localizer.text("statistics.points"),
        localizer.text("statistics.coverage"),
        localizer.text("statistics.minimum"),
        localizer.text("statistics.maximum"),
        localizer.text("statistics.mean"),
    )


def statistics_rows(
    statistics: tuple[CurveIntervalStatistics, ...],
    *,
    display_names: Mapping[str, str] | None = None,
) -> tuple[tuple[object, ...], ...]:
    labels = display_names or {}
    return tuple(
        (
            labels.get(item.mnemonic, item.mnemonic),
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
    display_names: Mapping[str, str] | None = None,
    language: AppLanguage = AppLanguage.EN,
) -> str:
    localizer = Localizer.create(language)
    lines = [
        f"{localizer.text('statistics.dataset_header')}\t{dataset_name}",
        f"{localizer.text('statistics.interval_header')}\t{interval_label}",
    ]
    lines.append("\t".join(statistics_columns(language)))
    for row in statistics_rows(statistics, display_names=display_names):
        lines.append("\t".join(_text(value) for value in row))
    return "\n".join(lines)


def export_interval_statistics_csv(
    path: str | Path,
    statistics: tuple[CurveIntervalStatistics, ...],
    *,
    interval_label: str,
    dataset_name: str,
    display_names: Mapping[str, str] | None = None,
    language: AppLanguage = AppLanguage.EN,
) -> Path:
    target = Path(path)
    localizer = Localizer.create(language)
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow((localizer.text("statistics.dataset_header"), dataset_name))
        writer.writerow((localizer.text("statistics.interval_header"), interval_label))
        writer.writerow(())
        writer.writerow(statistics_columns(language))
        writer.writerows(statistics_rows(statistics, display_names=display_names))
    return target


def export_interval_statistics_xlsx(
    path: str | Path,
    statistics: tuple[CurveIntervalStatistics, ...],
    *,
    interval_label: str,
    dataset_name: str,
    display_names: Mapping[str, str] | None = None,
    language: AppLanguage = AppLanguage.EN,
) -> Path:
    target = Path(path)
    localizer = Localizer.create(language)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = localizer.text("statistics.sheet_title")
    sheet.append((localizer.text("statistics.dataset_header"), dataset_name))
    sheet.append((localizer.text("statistics.interval_header"), interval_label))
    sheet.append(())
    sheet.append(statistics_columns(language))
    for row in statistics_rows(statistics, display_names=display_names):
        sheet.append(row)

    header_fill = PatternFill("solid", fgColor="DCE6F1")
    for cell in sheet[4]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
    widths = (34, 18, 14, 14, 14, 16, 16, 16)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width
    for row in sheet.iter_rows(min_row=5, min_col=5, max_col=8):
        for cell in row:
            cell.number_format = "0.########"
    sheet.freeze_panes = "A5"
    sheet.auto_filter.ref = f"A4:H{max(4, sheet.max_row)}"
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
