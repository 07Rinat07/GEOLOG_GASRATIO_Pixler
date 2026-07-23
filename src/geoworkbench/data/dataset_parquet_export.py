from __future__ import annotations

import json
import os
import tempfile
from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np

from geoworkbench.domain.models import Dataset, IndexType
from geoworkbench.services.coverage import analyze_curve_coverage


class DatasetParquetExportError(RuntimeError):
    pass


def export_dataset_parquet(
    dataset: Dataset, target: str | Path, *, overwrite: bool = False
) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != ".parquet":
        raise DatasetParquetExportError(
            "Неподдерживаемое расширение экспорта: " + destination.suffix
        )
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    try:
        pa = import_module("pyarrow")
        parquet = import_module("pyarrow.parquet")
    except ImportError as exc:
        raise DatasetParquetExportError(
            "Для Parquet установите optional-зависимости: pip install -e '.[analysis]'"
        ) from exc

    names: list[str] = []
    arrays: list[Any] = []
    column_metadata: dict[str, dict[str, Any]] = {}
    for index_id, index in dataset.indexes.items():
        name = _unique_column_name(index.mnemonic, index_id, names)
        names.append(name)
        values = (
            index.values.astype("datetime64[ns]")
            if index.index_type is IndexType.DATETIME
            else _nullable_numbers(index.values)
        )
        arrays.append(pa.array(values, from_pandas=True))
        column_metadata[name] = {
            "kind": "index",
            "index_id": index_id,
            "index_type": index.index_type.value,
            "role": index.role.value,
            "unit": index.unit,
            "confidence": float(index.confidence),
            "evidence": list(index.evidence),
            "datetime_format": index.datetime_format,
            "timezone": index.timezone,
        }
    for curve_id, curve in dataset.curves.items():
        name = _unique_column_name(curve.metadata.original_mnemonic, curve_id, names)
        names.append(name)
        arrays.append(pa.array(_nullable_numbers(curve.values), from_pandas=True))
        coverage = analyze_curve_coverage(
            curve, np.arange(curve.values.size, dtype=np.int64)
        )
        column_metadata[name] = {
            "kind": "curve",
            "curve_id": curve_id,
            "canonical_mnemonic": curve.metadata.canonical_mnemonic,
            "unit": curve.metadata.unit,
            "description": curve.metadata.description,
            "provenance": curve.metadata.provenance,
            "version": curve.version,
            "state": curve.state.value,
            "coverage": coverage.payload(),
        }
    metadata = {
        b"geoworkbench.format": b"geoworkbench.dataset.parquet.v1",
        b"geoworkbench.dataset": json.dumps(
            {
                "dataset_id": dataset.dataset_id,
                "name": dataset.name,
                "kind": dataset.kind.value,
                "depth_domain": dataset.depth_domain.value,
                "active_index_id": dataset.active_index_id,
                "source_path": str(dataset.source_path) if dataset.source_path else None,
                "version_headers": dataset.version_headers,
                "headers": dataset.headers,
                "parameters": dataset.parameters,
                "columns": column_metadata,
            },
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8"),
    }
    table = pa.Table.from_arrays(arrays, names=names).replace_schema_metadata(metadata)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(name)
    try:
        parquet.write_table(table, temporary)
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise DatasetParquetExportError(
            f"Не удалось экспортировать Parquet: {destination}"
        ) from exc
    return destination


def _nullable_numbers(values: np.ndarray[Any, Any]) -> list[int | float | None]:
    result: list[int | float | None] = []
    for value in values:
        if isinstance(value, (int, np.integer)):
            result.append(int(value))
            continue
        number = float(value)
        result.append(number if np.isfinite(number) else None)
    return result


def _unique_column_name(preferred: str, identifier: str, existing: list[str]) -> str:
    if preferred not in existing:
        return preferred
    candidate = f"{preferred}__{identifier}"
    suffix = 2
    while candidate in existing:
        candidate = f"{preferred}__{identifier}_{suffix}"
        suffix += 1
    return candidate
