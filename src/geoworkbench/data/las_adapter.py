from __future__ import annotations

from pathlib import Path

import lasio
import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    new_id,
)


class LasImportError(RuntimeError):
    pass


def import_las(path: str | Path, kind: DatasetKind = DatasetKind.GTI) -> Dataset:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() != ".las":
        raise LasImportError(f"Ожидался LAS-файл, получен: {source.suffix}")

    try:
        las = lasio.read(source, ignore_header_errors=True)
        frame = las.df()
    except Exception as exc:
        raise LasImportError(f"Не удалось прочитать LAS-файл: {source}") from exc

    depth = frame.index.to_numpy(dtype=np.float64, copy=True)
    dataset_id = new_id()
    dataset = Dataset(
        dataset_id=dataset_id,
        name=source.stem,
        kind=kind,
        depth_domain=DepthDomain.MD,
        depth=depth,
        source_path=source,
    )

    curve_sections = {str(item.mnemonic): item for item in las.curves}
    for column in frame.columns:
        item = curve_sections.get(str(column))
        curve_id = new_id()
        dataset.curves[curve_id] = CurveData(
            metadata=CurveMetadata(
                curve_id=curve_id,
                original_mnemonic=str(column),
                canonical_mnemonic=str(column).upper(),
                unit=str(item.unit) if item and item.unit else None,
                description=str(item.descr) if item and item.descr else None,
                source_dataset_id=dataset_id,
            ),
            values=frame[column].to_numpy(dtype=np.float64, copy=True),
        )

    dataset.headers = {str(item.mnemonic): str(item.value) for item in las.well}
    dataset.parameters = {str(item.mnemonic): str(item.value) for item in las.params}
    return dataset
