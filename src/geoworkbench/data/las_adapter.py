from __future__ import annotations

import os
import tempfile
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


class LasExportError(RuntimeError):
    pass


def import_las(path: str | Path, kind: DatasetKind = DatasetKind.GTI) -> Dataset:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() != ".las":
        raise LasImportError(f"Ожидался LAS-файл, получен: {source.suffix}")

    try:
        las = lasio.read(source, ignore_header_errors=True)
        depth = np.asarray(las.index, dtype=np.float64).copy()
    except Exception as exc:
        raise LasImportError(f"Не удалось прочитать LAS-файл: {source}") from exc

    dataset_id = new_id()
    dataset = Dataset(
        dataset_id=dataset_id,
        name=source.stem,
        kind=kind,
        depth_domain=DepthDomain.MD,
        depth=depth,
        source_path=source,
    )

    try:
        for item in list(las.curves)[1:]:
            mnemonic = str(item.mnemonic)
            values = np.asarray(las[mnemonic], dtype=np.float64).copy()
            if values.shape != depth.shape:
                raise ValueError(f"Размер кривой {mnemonic} не совпадает со шкалой глубины")
            curve_id = new_id()
            dataset.curves[curve_id] = CurveData(
                metadata=CurveMetadata(
                    curve_id=curve_id,
                    original_mnemonic=mnemonic,
                    canonical_mnemonic=mnemonic.upper(),
                    unit=str(item.unit) if item.unit else None,
                    description=str(item.descr) if item.descr else None,
                    source_dataset_id=dataset_id,
                ),
                values=values,
            )
        dataset.headers = {str(item.mnemonic): str(item.value) for item in las.well}
        dataset.parameters = {str(item.mnemonic): str(item.value) for item in las.params}
    except Exception as exc:
        raise LasImportError(f"Некорректные данные LAS-файла: {source}") from exc
    return dataset


def export_las(
    dataset: Dataset,
    target: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != ".las":
        raise LasExportError("Файл экспорта должен иметь расширение .las")
    if dataset.source_path is not None and _same_path(destination, dataset.source_path):
        raise LasExportError("Исходный LAS нельзя перезаписывать")
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    if dataset.depth.ndim != 1:
        raise LasExportError("Шкала глубины должна быть одномерной")

    mnemonics: set[str] = {"dept"}
    for curve in dataset.curves.values():
        mnemonic = curve.metadata.original_mnemonic.strip()
        normalized = mnemonic.casefold()
        if not mnemonic:
            raise LasExportError("Мнемоника кривой не может быть пустой")
        if normalized in mnemonics:
            raise LasExportError(f"Повторяющаяся или зарезервированная мнемоника: {mnemonic}")
        if curve.values.shape != dataset.depth.shape:
            raise LasExportError(f"Размер кривой {mnemonic} не совпадает со шкалой глубины")
        mnemonics.add(normalized)

    destination.parent.mkdir(parents=True, exist_ok=True)
    las = _build_las_file(dataset)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(fd)
    try:
        las.write(temporary_name, version=2.0)
        os.replace(temporary_name, destination)
    except Exception as exc:
        Path(temporary_name).unlink(missing_ok=True)
        raise LasExportError(f"Не удалось экспортировать LAS: {destination}") from exc
    return destination


def _build_las_file(dataset: Dataset) -> lasio.LASFile:
    las = lasio.LASFile()
    depth_unit = "ms" if dataset.depth_domain is DepthDomain.TIME else "m"
    las.append_curve("DEPT", np.asarray(dataset.depth, dtype=np.float64), unit=depth_unit)
    for curve in dataset.curves.values():
        las.append_curve(
            curve.metadata.original_mnemonic.strip(),
            np.asarray(curve.values, dtype=np.float64),
            unit=curve.metadata.unit or "",
            descr=curve.metadata.description or "",
        )
    _apply_header_values(las.well, dataset.headers)
    _apply_header_values(las.params, dataset.parameters)
    return las


def _apply_header_values(section, values: dict[str, str]) -> None:
    for mnemonic, value in values.items():
        try:
            section[mnemonic].value = value
        except KeyError:
            section.append(lasio.HeaderItem(mnemonic, "", value, ""))


def _same_path(first: Path, second: Path) -> bool:
    return first.expanduser().resolve(strict=False) == second.expanduser().resolve(strict=False)
