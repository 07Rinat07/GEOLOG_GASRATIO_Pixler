from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from openpyxl import Workbook  # type: ignore[import-untyped]

from geoworkbench.domain.models import WellInterpretation


class InterpretationExportError(RuntimeError):
    """Raised when an interpretation interval package cannot be exported."""


_COLUMNS = (
    "interval_id",
    "top_depth",
    "bottom_depth",
    "interval_type",
    "label",
    "color",
    "comment",
)


def export_interpretation_json(
    interpretation: WellInterpretation,
    target: str | Path,
    *,
    well_name: str | None = None,
    overwrite: bool = False,
) -> Path:
    destination = _prepare_target(target, ".json", overwrite=overwrite)
    payload = {
        "schema": "geolog.interpretation.intervals.v1",
        "well_name": well_name,
        "interpretation": asdict(interpretation),
    }
    try:
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise InterpretationExportError(
            f"Не удалось экспортировать интерпретацию: {destination}"
        ) from exc
    return destination


def export_interpretation_csv(
    interpretation: WellInterpretation,
    target: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    destination = _prepare_target(target, ".csv", overwrite=overwrite)
    try:
        with destination.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=_COLUMNS)
            writer.writeheader()
            for interval in interpretation.intervals:
                row = asdict(interval)
                row["comment"] = row["comment"] or ""
                writer.writerow(row)
    except OSError as exc:
        raise InterpretationExportError(
            f"Не удалось экспортировать интерпретацию: {destination}"
        ) from exc
    return destination


def export_interpretation_excel(
    interpretation: WellInterpretation,
    target: str | Path,
    *,
    well_name: str | None = None,
    overwrite: bool = False,
) -> Path:
    destination = _prepare_target(target, ".xlsx", overwrite=overwrite)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Intervals"
    sheet.append(list(_COLUMNS))
    for interval in interpretation.intervals:
        row = asdict(interval)
        sheet.append([row[column] if row[column] is not None else "" for column in _COLUMNS])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    widths = (38, 14, 14, 22, 32, 12, 60)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width

    meta = workbook.create_sheet("Metadata")
    meta.append(["well_name", well_name or ""])
    meta.append(["interpretation_id", interpretation.interpretation_id])
    meta.append(["name", interpretation.name])
    meta.append(["description", interpretation.description or ""])
    try:
        workbook.save(destination)
    except OSError as exc:
        raise InterpretationExportError(
            f"Не удалось экспортировать интерпретацию: {destination}"
        ) from exc
    return destination


def _prepare_target(target: str | Path, suffix: str, *, overwrite: bool) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != suffix:
        destination = destination.with_suffix(suffix)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination
