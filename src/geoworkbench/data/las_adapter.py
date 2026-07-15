from __future__ import annotations

import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

import lasio
import numpy as np

from geoworkbench.data.las_import_report import (
    LasImportIssue,
    LasImportReport,
    LasIssueSeverity,
    LasSourceSnapshot,
)
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
    new_id,
)
from geoworkbench.services.depth_axis import DepthAxisReport, DepthDirection, analyze_depth_axis


class LasImportError(RuntimeError):
    pass


class LasExportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LasImportResult:
    dataset: Dataset
    report: LasImportReport


def import_las(path: str | Path, kind: DatasetKind = DatasetKind.GTI) -> Dataset:
    """Import a LAS dataset while preserving the original public API."""

    return import_las_with_report(path, kind).dataset


def import_las_with_report(
    path: str | Path,
    kind: DatasetKind = DatasetKind.GTI,
) -> LasImportResult:
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
    size_bytes, source_sha256 = _source_fingerprint(source)
    report = _build_import_report(source, size_bytes, source_sha256, las, depth)
    return LasImportResult(dataset=dataset, report=report)


def _build_import_report(
    source: Path,
    size_bytes: int,
    source_sha256: str,
    las: Any,
    depth: np.ndarray,
) -> LasImportReport:
    depth_report = analyze_depth_axis(depth)
    version = _section_value(getattr(las, "version", ()), "VERS")
    wrap = _section_value(getattr(las, "version", ()), "WRAP")
    null_text = _section_value(getattr(las, "well", ()), "NULL")
    snapshot = LasSourceSnapshot(
        path=source,
        size_bytes=size_bytes,
        sha256=source_sha256,
        las_version=version,
        wrap=wrap,
        null_value=_optional_float(null_text),
    )
    issues: list[LasImportIssue] = []

    if version is None:
        issues.append(_warning("missing-version", "В LAS не удалось определить версию VERS"))
    elif not version.startswith(("1.2", "2.")):
        issues.append(
            _warning(
                "partial-version-support",
                f"LAS {version} открыт в режиме ограниченной совместимости",
            )
        )
    if snapshot.null_value is None:
        issues.append(_warning("missing-null", "Не удалось определить числовое значение NULL"))

    curve_names = [str(item.mnemonic).strip().casefold() for item in getattr(las, "curves", ())]
    duplicates = sorted(name for name, count in Counter(curve_names).items() if name and count > 1)
    if duplicates:
        issues.append(
            _warning(
                "duplicate-mnemonics",
                "Повторяющиеся мнемоники кривых: " + ", ".join(duplicates),
            )
        )

    direction_messages = {
        DepthDirection.DESCENDING: "Индекс записан по убыванию; исходные данные не изменены",
        DepthDirection.MIXED: "Индекс имеет смешанное направление",
        DepthDirection.CONSTANT: "Все конечные значения индекса одинаковы",
        DepthDirection.UNKNOWN: "Направление индекса определить невозможно",
    }
    if depth_report.direction in direction_messages:
        issues.append(
            _warning(
                f"index-{depth_report.direction}",
                direction_messages[depth_report.direction],
            )
        )
    if depth_report.duplicate_count:
        issues.append(
            _warning(
                "duplicate-index-values",
                f"Повторяющихся значений индекса: {depth_report.duplicate_count}",
            )
        )
    if depth_report.missing_count:
        issues.append(
            _warning(
                "missing-index-values",
                f"Пропущенных значений индекса: {depth_report.missing_count}",
            )
        )
    if not depth_report.is_uniform and depth.size > 1:
        issues.append(_warning("non-uniform-step", "Шаг индекса не является равномерным"))
    if depth_report.gap_count:
        issues.append(_warning("index-gaps", f"Обнаружено разрывов индекса: {depth_report.gap_count}"))

    _append_header_mismatches(issues, las, depth_report)
    return LasImportReport(snapshot, depth_report, tuple(issues))


def _append_header_mismatches(
    issues: list[LasImportIssue],
    las: Any,
    report: DepthAxisReport,
) -> None:
    for mnemonic, actual, label in (
        ("STRT", report.start, "STRT"),
        ("STOP", report.stop, "STOP"),
        ("STEP", report.nominal_step, "STEP"),
    ):
        declared = _optional_float(_section_value(getattr(las, "well", ()), mnemonic))
        if declared is None or actual is None:
            continue
        if mnemonic == "STEP":
            actual = -actual if report.direction is DepthDirection.DESCENDING else actual
        tolerance = max(abs(declared), abs(actual), 1.0) * 1e-6
        if not np.isclose(declared, actual, rtol=0.0, atol=tolerance):
            issues.append(
                _warning(
                    f"header-{mnemonic.casefold()}-mismatch",
                    f"{label} в заголовке ({declared:g}) не совпадает с данными ({actual:g})",
                )
            )


def _section_value(section: Iterable[Any], mnemonic: str) -> str | None:
    wanted = mnemonic.casefold()
    for item in section:
        if str(getattr(item, "mnemonic", "")).strip().casefold() == wanted:
            value = str(getattr(item, "value", "")).strip()
            return value or None
    return None


def _optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if np.isfinite(parsed) else None


def _warning(code: str, message: str) -> LasImportIssue:
    return LasImportIssue(code, LasIssueSeverity.WARNING, message)


def _source_fingerprint(source: Path) -> tuple[int, str]:
    digest = sha256()
    size_bytes = 0
    with source.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size_bytes += len(chunk)
            digest.update(chunk)
    return size_bytes, digest.hexdigest()


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
