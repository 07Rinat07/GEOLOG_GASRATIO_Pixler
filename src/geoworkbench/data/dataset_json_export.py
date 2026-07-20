from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from geoworkbench.domain.models import Dataset, IndexType


class DatasetJsonExportError(RuntimeError):
    pass


def dataset_to_json_dict(dataset: Dataset) -> dict[str, Any]:
    return {
        "format": "geoworkbench.dataset",
        "format_version": 1,
        "dataset": {
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "kind": dataset.kind.value,
            "depth_domain": dataset.depth_domain.value,
            "source_path": str(dataset.source_path) if dataset.source_path else None,
            "active_index_id": dataset.active_index_id,
            "version_headers": dict(dataset.version_headers),
            "headers": dict(dataset.headers),
            "parameters": dict(dataset.parameters),
            "indexes": {
                index_id: {
                    "index_id": index.index_id,
                    "mnemonic": index.mnemonic,
                    "index_type": index.index_type.value,
                    "role": index.role.value,
                    "unit": index.unit,
                    "values": _index_values(index.index_type, index.values),
                    "confidence": float(index.confidence),
                    "evidence": list(index.evidence),
                    "datetime_format": index.datetime_format,
                    "timezone": index.timezone,
                }
                for index_id, index in dataset.indexes.items()
            },
            "curves": {
                curve_id: {
                    "metadata": {
                        "curve_id": curve.metadata.curve_id,
                        "original_mnemonic": curve.metadata.original_mnemonic,
                        "canonical_mnemonic": curve.metadata.canonical_mnemonic,
                        "unit": curve.metadata.unit,
                        "description": curve.metadata.description,
                        "source_dataset_id": curve.metadata.source_dataset_id,
                        "provenance": curve.metadata.provenance,
                    },
                    "values": [_finite_number(value) for value in curve.values],
                    "version": curve.version,
                    "state": curve.state.value,
                }
                for curve_id, curve in dataset.curves.items()
            },
        },
    }


def export_dataset_json(dataset: Dataset, target: str | Path, *, overwrite: bool = False) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != ".json":
        raise DatasetJsonExportError("Неподдерживаемое расширение экспорта: " + destination.suffix)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                dataset_to_json_dict(dataset),
                stream,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise DatasetJsonExportError(f"Не удалось экспортировать JSON: {destination}") from exc
    return destination


def _index_values(index_type: IndexType, values: np.ndarray[Any, Any]) -> list[object]:
    if index_type is IndexType.DATETIME:
        nanoseconds = values.astype("datetime64[ns]")
        return [
            None if np.isnat(value) else np.datetime_as_string(value, unit="ns")
            for value in nanoseconds
        ]
    return [_finite_number(value) for value in values]


def _finite_number(value: Any) -> int | float | None:
    if isinstance(value, (int, np.integer)):
        return int(value)
    number = float(value)
    return number if np.isfinite(number) else None
