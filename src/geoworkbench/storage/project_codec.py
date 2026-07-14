from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from geoworkbench.domain.models import (
    CalculationState,
    CanvasObject,
    CurveData,
    CurveMetadata,
    CuttingsComponent,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
    LithologyInterval,
    Project,
    StratigraphyInterval,
    Well,
)


class ProjectFormatError(RuntimeError):
    """Raised when a project JSON file cannot be safely reconstructed."""


def _required(data: dict[str, Any], key: str, expected: type) -> Any:
    value = data.get(key)
    if not isinstance(value, expected):
        raise ProjectFormatError(f"Поле '{key}' отсутствует или имеет неверный тип")
    return value


def _curve_from_dict(data: dict[str, Any]) -> CurveData:
    metadata_data = _required(data, "metadata", dict)
    metadata = CurveMetadata(
        curve_id=str(_required(metadata_data, "curve_id", str)),
        original_mnemonic=str(_required(metadata_data, "original_mnemonic", str)),
        canonical_mnemonic=metadata_data.get("canonical_mnemonic"),
        unit=metadata_data.get("unit"),
        description=metadata_data.get("description"),
        source_dataset_id=str(_required(metadata_data, "source_dataset_id", str)),
        provenance=str(metadata_data.get("provenance", "source")),
    )
    values = np.asarray(_required(data, "values", list), dtype=np.float64)
    try:
        state = CalculationState(str(data.get("state", CalculationState.CURRENT.value)))
    except ValueError as exc:
        raise ProjectFormatError(f"Неизвестное состояние кривой: {data.get('state')}") from exc
    return CurveData(
        metadata=metadata,
        values=values,
        version=int(data.get("version", 1)),
        state=state,
    )


def _dataset_from_dict(data: dict[str, Any]) -> Dataset:
    try:
        kind = DatasetKind(str(_required(data, "kind", str)))
        depth_domain = DepthDomain(str(_required(data, "depth_domain", str)))
    except ValueError as exc:
        raise ProjectFormatError("Неизвестный тип набора данных или шкалы глубины") from exc

    dataset = Dataset(
        dataset_id=str(_required(data, "dataset_id", str)),
        name=str(_required(data, "name", str)),
        kind=kind,
        depth_domain=depth_domain,
        depth=np.asarray(_required(data, "depth", list), dtype=np.float64),
        source_path=Path(data["source_path"]) if data.get("source_path") else None,
        headers={str(k): str(v) for k, v in dict(data.get("headers", {})).items()},
        parameters={str(k): str(v) for k, v in dict(data.get("parameters", {})).items()},
    )
    curve_map = _required(data, "curves", dict)
    dataset.curves = {str(curve_id): _curve_from_dict(curve) for curve_id, curve in curve_map.items()}
    for curve in dataset.curves.values():
        if curve.values.shape != dataset.depth.shape:
            raise ProjectFormatError(
                f"Кривая {curve.metadata.original_mnemonic} имеет длину {len(curve.values)}, "
                f"а шкала глубины — {len(dataset.depth)}"
            )
    return dataset


def _well_from_dict(data: dict[str, Any]) -> Well:
    well = Well(
        well_id=str(_required(data, "well_id", str)),
        name=str(_required(data, "name", str)),
    )
    datasets = _required(data, "datasets", dict)
    well.datasets = {str(dataset_id): _dataset_from_dict(item) for dataset_id, item in datasets.items()}
    well.lithology = [LithologyInterval(**item) for item in data.get("lithology", [])]
    well.cuttings = [
        CuttingsSample(
            sample_id=item["sample_id"],
            top_depth=float(item["top_depth"]),
            bottom_depth=float(item["bottom_depth"]),
            components=[CuttingsComponent(**component) for component in item.get("components", [])],
            lba_type_id=item.get("lba_type_id"),
            lba_intensity=item.get("lba_intensity"),
            description=item.get("description"),
        )
        for item in data.get("cuttings", [])
    ]
    well.stratigraphy = [StratigraphyInterval(**item) for item in data.get("stratigraphy", [])]
    well.canvas_objects = [CanvasObject(**item) for item in data.get("canvas_objects", [])]
    return well


def project_from_dict(data: dict[str, Any]) -> Project:
    project = Project(
        project_id=str(_required(data, "project_id", str)),
        name=str(_required(data, "name", str)),
    )
    wells = _required(data, "wells", dict)
    project.wells = {str(well_id): _well_from_dict(item) for well_id, item in wells.items()}
    return project


def load_project(path: str | Path, *, max_size_mb: int = 512) -> Project:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.stat().st_size > max_size_mb * 1024 * 1024:
        raise ProjectFormatError(f"Файл проекта превышает лимит {max_size_mb} МБ")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectFormatError(f"Не удалось прочитать проект: {source}") from exc
    if not isinstance(raw, dict):
        raise ProjectFormatError("Корень проекта должен быть JSON-объектом")
    return project_from_dict(raw)
