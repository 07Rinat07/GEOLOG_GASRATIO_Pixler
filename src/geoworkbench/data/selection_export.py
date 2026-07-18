from __future__ import annotations

import csv
import os
import tempfile
from copy import copy
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from openpyxl import Workbook  # type: ignore[import-untyped]

from geoworkbench.domain.models import CurveData, Dataset, DatasetIndex, IndexRole, IndexType
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
    export_indexes = _excel_indexes(dataset)
    header: list[object] = [
        _index_header(index, primary=index.index_id == dataset.active_index_id)
        for index in export_indexes
    ]
    header.extend(_curve_headers(curves))
    rows: list[list[object]] = [header]
    rows.extend(
        [_excel_index_value(index_value, int(index)) for index_value in export_indexes]
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
    for index in export_indexes:
        metadata.extend(
            [
                [f"Index {index.mnemonic}", index.index_type.value],
                [f"Source timezone {index.mnemonic}", index.timezone or ""],
            ]
        )
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
    return [_index_header(dataset.active_index, primary=True), *_curve_headers(curves)]


def _curve_headers(curves: list[CurveData]) -> list[str]:
    return [
        f"{curve.metadata.original_mnemonic} [{curve.metadata.unit}]"
        if curve.metadata.unit
        else curve.metadata.original_mnemonic
        for curve in curves
    ]


def _index_header(index: DatasetIndex, *, primary: bool) -> str:
    qualifier = (
        "UTC"
        if index.index_type is IndexType.DATETIME and index.timezone is not None
        else index.unit or ""
    )
    mnemonic = "DEPTH" if primary and index.role is IndexRole.DEPTH else index.mnemonic
    return f"{mnemonic} [{qualifier}]" if qualifier else mnemonic


def _excel_indexes(dataset: Dataset) -> tuple[DatasetIndex, ...]:
    return (
        dataset.active_index,
        *(
            index
            for index in dataset.indexes.values()
            if index.index_id != dataset.active_index_id and index.role is IndexRole.TIME
        ),
    )


def _number(value: float) -> str:
    return "" if not np.isfinite(value) else f"{float(value):.15g}"


def _excel_index_value(index: DatasetIndex, row: int) -> object:
    if index.role is not IndexRole.TIME or index.index_type is not IndexType.DATETIME:
        value = np.asarray(index.values)[row]
        return None if not np.isfinite(value) else float(value)
    value = np.asarray(index.values)[row].astype("datetime64[ns]")
    if np.isnat(value):
        return None
    nanoseconds = int(value.astype(np.int64))
    seconds, remainder = divmod(nanoseconds, 1_000_000_000)
    return datetime(1970, 1, 1) + timedelta(
        seconds=seconds, microseconds=remainder // 1_000
    )


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
    workbook = Workbook()
    data_sheet = workbook.active
    data_sheet.title = "Data"
    for row in data_rows:
        data_sheet.append(row)
    for cell in data_sheet[1]:
        font = copy(cell.font)
        font.bold = True
        cell.font = font
    for row in data_sheet.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, datetime):
                cell.number_format = "yyyy-mm-dd hh:mm:ss.000"
    data_sheet.freeze_panes = "A2"
    metadata_sheet = workbook.create_sheet("Metadata")
    for row in metadata_rows:
        metadata_sheet.append(row)
    workbook.save(path)
