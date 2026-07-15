from __future__ import annotations

import csv
import os
import tempfile
import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

import numpy as np

from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.services.dataset_selection import depth_interval_indices


class SelectionExportError(RuntimeError):
    pass


def export_selection_text(
    dataset: Dataset,
    target: str | Path,
    curve_ids: list[str],
    depth_top: float,
    depth_bottom: float,
    *,
    delimiter: str = "\t",
    overwrite: bool = False,
) -> Path:
    if len(delimiter) != 1:
        raise ValueError("Разделитель должен состоять из одного символа")
    destination = Path(target)
    _validate_destination(destination, {".txt", ".csv"}, overwrite)
    indices, curves = _selection(dataset, curve_ids, depth_top, depth_bottom)
    temporary = _temporary_path(destination)
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, delimiter=delimiter)
            writer.writerow(_headers(dataset, curves))
            for index in indices:
                writer.writerow(
                    [_number(dataset.depth[index])]
                    + [_number(curve.values[index]) for curve in curves]
                )
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise SelectionExportError(f"Не удалось экспортировать интервал: {destination}") from exc
    return destination


def export_selection_excel(
    dataset: Dataset,
    target: str | Path,
    curve_ids: list[str],
    depth_top: float,
    depth_bottom: float,
    *,
    overwrite: bool = False,
) -> Path:
    destination = Path(target)
    _validate_destination(destination, {".xlsx"}, overwrite)
    indices, curves = _selection(dataset, curve_ids, depth_top, depth_bottom)
    rows: list[list[object]] = [list(_headers(dataset, curves))]
    rows.extend(
        [float(dataset.depth[index])]
        + [None if not np.isfinite(curve.values[index]) else float(curve.values[index]) for curve in curves]
        for index in indices
    )
    metadata: list[list[object]] = [
        ["Dataset", dataset.name],
        ["Depth top", depth_top],
        ["Depth bottom", depth_bottom],
        ["Rows", int(indices.size)],
        ["Source", str(dataset.source_path or "")],
    ]
    temporary = _temporary_path(destination)
    try:
        _write_xlsx(temporary, rows, metadata)
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise SelectionExportError(f"Не удалось экспортировать Excel: {destination}") from exc
    return destination


def _selection(
    dataset: Dataset, curve_ids: list[str], depth_top: float, depth_bottom: float
) -> tuple[np.ndarray, list[CurveData]]:
    if not curve_ids:
        raise ValueError("Выберите хотя бы один параметр")
    missing = [curve_id for curve_id in curve_ids if curve_id not in dataset.curves]
    if missing:
        raise KeyError(f"Кривые не найдены: {', '.join(missing)}")
    indices = depth_interval_indices(dataset, depth_top, depth_bottom)
    return indices, [dataset.curves[curve_id] for curve_id in curve_ids]


def _headers(dataset: Dataset, curves: list[CurveData]) -> list[object]:
    depth_unit = "ms" if dataset.depth_domain.value == "time" else "m"
    result: list[object] = [f"DEPTH [{depth_unit}]"]
    result.extend(
        f"{curve.metadata.original_mnemonic} [{curve.metadata.unit}]"
        if curve.metadata.unit
        else curve.metadata.original_mnemonic
        for curve in curves
    )
    return result


def _number(value: float) -> str:
    return "" if not np.isfinite(value) else f"{float(value):.15g}"


def _validate_destination(destination: Path, suffixes: set[str], overwrite: bool) -> None:
    if destination.suffix.casefold() not in suffixes:
        raise SelectionExportError(
            "Неподдерживаемое расширение экспорта: " + destination.suffix
        )
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)


def _temporary_path(destination: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    return Path(name)


def _write_xlsx(path: Path, data_rows: list[list[object]], metadata_rows: list[list[object]]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types())
        archive.writestr("_rels/.rels", _root_relationships())
        archive.writestr("xl/workbook.xml", _workbook())
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships())
        archive.writestr("xl/worksheets/sheet1.xml", _worksheet(data_rows))
        archive.writestr("xl/worksheets/sheet2.xml", _worksheet(metadata_rows))


def _worksheet(rows: list[list[object]]) -> bytes:
    root = Element("worksheet", xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main")
    sheet_data = SubElement(root, "sheetData")
    for row_number, values in enumerate(rows, start=1):
        row = SubElement(sheet_data, "row", r=str(row_number))
        for column_number, value in enumerate(values, start=1):
            reference = f"{_column_name(column_number)}{row_number}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cell = SubElement(row, "c", r=reference)
                SubElement(cell, "v").text = str(value)
            else:
                cell = SubElement(row, "c", r=reference, t="inlineStr")
                inline = SubElement(cell, "is")
                SubElement(inline, "t").text = "" if value is None else str(value)
    return tostring(root, encoding="utf-8", xml_declaration=True)


def _column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _content_types() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""


def _root_relationships() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def _workbook() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Data" sheetId="1" r:id="rId1"/><sheet name="Metadata" sheetId="2" r:id="rId2"/></sheets>
</workbook>"""


def _workbook_relationships() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>"""
