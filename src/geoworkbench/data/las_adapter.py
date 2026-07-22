from __future__ import annotations

import os
import tempfile
from collections import Counter
from dataclasses import dataclass
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
from geoworkbench.data.las_export_plan import LasExportPlan, analyze_las_export
from geoworkbench.data.lossless_las import (
    LasSectionEditError,
    LosslessLasDocument,
    NewlineStyle,
    parse_lossless_las,
    read_lossless_las,
    replace_section_roles,
    section_role,
)
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    new_id,
)
from geoworkbench.services.depth_axis import DepthAxisReport, DepthDirection, analyze_depth_axis
from geoworkbench.services.index_detection import IndexColumn, detect_index_candidates
from geoworkbench.services.las_parameter_resolver import infer_canonical_mnemonic
from geoworkbench.services.text_normalization import clean_display_text, clean_mnemonic


class LasImportError(RuntimeError):
    pass


class LasExportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LasImportResult:
    dataset: Dataset
    report: LasImportReport
    source_document: LosslessLasDocument


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
        source_document = read_lossless_las(source)
        las = lasio.read(
            source,
            ignore_header_errors=True,
            encoding=source_document.encoding,
            encoding_errors="replace",
            autodetect_encoding=False,
        )
        depth = np.asarray(las.index, dtype=np.float64).copy()
    except Exception as exc:
        raise LasImportError(f"Не удалось прочитать LAS-файл: {source}") from exc

    index_curve = list(las.curves)[0]
    index_candidate = detect_index_candidates(
        (
            IndexColumn(
                curve_id="source-index",
                mnemonic=clean_mnemonic(index_curve.mnemonic, fallback="DEPT"),
                unit=clean_display_text(index_curve.unit) if index_curve.unit else None,
                description=clean_display_text(index_curve.descr) if index_curve.descr else None,
                values=depth,
            ),
        )
    )[0]
    depth_domain = (
        _candidate_depth_domain(index_candidate.role, index_candidate.index_type)
        if index_candidate.confidence >= 0.7
        else DepthDomain.MD
    )
    dataset_id = new_id()
    dataset = Dataset(
        dataset_id=dataset_id,
        name=source.stem,
        kind=kind,
        depth_domain=depth_domain,
        depth=depth,
        source_path=source,
    )
    dataset.active_index.mnemonic = clean_mnemonic(index_curve.mnemonic, fallback="DEPT")
    dataset.active_index.unit = clean_display_text(index_curve.unit) if index_curve.unit else None
    dataset.active_index.confidence = index_candidate.confidence
    dataset.active_index.evidence = index_candidate.evidence
    dataset.active_index.datetime_format = index_candidate.datetime_format
    dataset.active_index.timezone = index_candidate.timezone
    if index_candidate.confidence >= 0.7:
        dataset.active_index.index_type = index_candidate.index_type
        dataset.active_index.role = index_candidate.role

    try:
        for item in list(las.curves)[1:]:
            raw_mnemonic = str(item.mnemonic)
            mnemonic = clean_mnemonic(raw_mnemonic)
            unit = clean_display_text(item.unit) if item.unit else ""
            description = clean_display_text(item.descr) if item.descr else ""
            values = np.asarray(las[raw_mnemonic], dtype=np.float64).copy()
            if values.shape != depth.shape:
                raise ValueError(f"Размер кривой {mnemonic} не совпадает со шкалой глубины")
            curve_id = new_id()
            canonical = infer_canonical_mnemonic(
                mnemonic,
                description=description,
                unit=unit,
            )
            dataset.curves[curve_id] = CurveData(
                metadata=CurveMetadata(
                    curve_id=curve_id,
                    original_mnemonic=mnemonic,
                    canonical_mnemonic=canonical or mnemonic.upper(),
                    unit=unit or None,
                    description=description or None,
                    source_dataset_id=dataset_id,
                ),
                values=values,
            )
        dataset.version_headers = {
            clean_mnemonic(item.mnemonic): clean_display_text(item.value) for item in las.version
        }
        dataset.headers = {
            clean_mnemonic(item.mnemonic): clean_display_text(item.value) for item in las.well
        }
        dataset.parameters = {
            clean_mnemonic(item.mnemonic): clean_display_text(item.value) for item in las.params
        }
    except Exception as exc:
        raise LasImportError(f"Некорректные данные LAS-файла: {source}") from exc
    report = _build_import_report(source, source_document, las, depth)
    return LasImportResult(dataset=dataset, report=report, source_document=source_document)


def _build_import_report(
    source: Path,
    source_document: LosslessLasDocument,
    las: Any,
    depth: np.ndarray,
) -> LasImportReport:
    depth_report = analyze_depth_axis(depth)
    version = _section_value(getattr(las, "version", ()), "VERS")
    wrap = _section_value(getattr(las, "version", ()), "WRAP")
    null_text = _section_value(getattr(las, "well", ()), "NULL")
    snapshot = LasSourceSnapshot(
        path=source,
        size_bytes=source_document.size_bytes,
        sha256=source_document.sha256,
        encoding=source_document.encoding,
        newline_style=source_document.newline_style,
        section_names=tuple(section.name for section in source_document.sections),
        las_version=version,
        wrap=wrap,
        null_value=_optional_float(null_text),
    )
    issues: list[LasImportIssue] = []

    _append_structure_issues(issues, source_document)

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
        issues.append(
            _warning("index-gaps", f"Обнаружено разрывов индекса: {depth_report.gap_count}")
        )

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


def _candidate_depth_domain(role: IndexRole, index_type: IndexType) -> DepthDomain:
    if role is IndexRole.TIME:
        return DepthDomain.TIME
    if index_type in {IndexType.MD, IndexType.TVD, IndexType.TVDSS}:
        return DepthDomain(index_type.value)
    return DepthDomain.MD


def _append_structure_issues(
    issues: list[LasImportIssue],
    document: LosslessLasDocument,
) -> None:
    if not document.sections:
        issues.append(_warning("missing-sections", "В исходнике не найдены секции LAS"))
        return
    names = [section.name for section in document.sections]
    counts = Counter(names)
    repeated = sorted(name for name, count in counts.items() if name and count > 1)
    if repeated:
        issues.append(
            _warning(
                "duplicate-sections",
                "Повторяющиеся секции LAS: " + ", ".join(repeated),
            )
        )
    ascii_aliases = {"a", "ascii", "ascii_log_data", "log_data"}
    if not any(name in ascii_aliases for name in names):
        issues.append(_warning("missing-ascii-section", "Не найдена секция данных ASCII"))
    if document.newline_style.value == "mixed":
        issues.append(_warning("mixed-newlines", "В исходнике смешаны типы перевода строк"))


def export_las(
    dataset: Dataset,
    target: str | Path,
    *,
    overwrite: bool = False,
    source_document: LosslessLasDocument | None = None,
    plan: LasExportPlan | None = None,
) -> Path:
    export_plan = plan or LasExportPlan()
    destination = Path(target)
    if destination.suffix.casefold() != ".las":
        raise LasExportError("Файл экспорта должен иметь расширение .las")
    if dataset.source_path is not None and _same_path(destination, dataset.source_path):
        raise LasExportError("Исходный LAS нельзя перезаписывать")
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    active_values = np.asarray(dataset.active_index.values)
    if active_values.ndim != 1:
        raise LasExportError("Индекс LAS должен быть одномерным")
    analysis = analyze_las_export(dataset, export_plan, source_document)
    if not analysis.can_export:
        raise LasExportError("; ".join(issue.message for issue in analysis.errors))

    index_mnemonic = _las_index_mnemonic(dataset)
    mnemonics: set[str] = {index_mnemonic.casefold()}
    for curve in dataset.curves.values():
        mnemonic = curve.metadata.original_mnemonic.strip()
        normalized = mnemonic.casefold()
        if not mnemonic:
            raise LasExportError("Мнемоника кривой не может быть пустой")
        if normalized in mnemonics:
            raise LasExportError(f"Повторяющаяся или зарезервированная мнемоника: {mnemonic}")
        if curve.values.shape != active_values.shape:
            raise LasExportError(f"Размер кривой {mnemonic} не совпадает с активным индексом")
        mnemonics.add(normalized)

    destination.parent.mkdir(parents=True, exist_ok=True)
    las = _build_las_file(dataset, null_value=export_plan.null_value)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(fd)
    try:
        # lasio opens a path with the operating-system default encoding. On
        # Windows this is commonly CP1251, while the lossless composer parses
        # the generated temporary file independently. Russian descriptions then
        # caused a hidden UnicodeDecodeError during external-LAS insertion.
        # Write the intermediate document explicitly as UTF-8 and let the
        # lossless layer convert sections back to the original source encoding.
        with Path(temporary_name).open("w", encoding="utf-8", newline="") as stream:
            las.write(
                stream,
                version=export_plan.version.writer_value,
                wrap=export_plan.wrap,
                fmt=export_plan.number_format,
            )
            stream.flush()
            os.fsync(stream.fileno())
        if source_document is not None and export_plan.preserve_custom_sections:
            generated = parse_lossless_las(Path(temporary_name).read_bytes())
            composed = _compose_lossless_export(source_document, generated)
            Path(temporary_name).write_bytes(composed.to_bytes())
        os.replace(temporary_name, destination)
    except LasExportError:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    except Exception as exc:
        Path(temporary_name).unlink(missing_ok=True)
        raise LasExportError(f"Не удалось экспортировать LAS: {destination}") from exc
    return destination


def _compose_lossless_export(
    source: LosslessLasDocument,
    generated: LosslessLasDocument,
) -> LosslessLasDocument:
    generated_by_role = {
        role: generated.section_bytes(section)
        for section in generated.sections
        if (role := section_role(section.name)) is not None
    }
    source_roles = {
        role for section in source.sections if (role := section_role(section.name)) is not None
    }
    required_roles = {"version", "well", "curve", "ascii"}
    missing = required_roles - source_roles
    if missing:
        raise LasExportError(
            "Lossless-экспорт невозможен: отсутствуют секции " + ", ".join(sorted(missing))
        )
    missing_generated = source_roles - set(generated_by_role)
    if missing_generated:
        raise LasExportError(
            "Lossless-экспорт невозможен: генератор не создал секции "
            + ", ".join(sorted(missing_generated))
        )
    replacements = {
        role: _adapt_generated_section(payload, source)
        for role, payload in generated_by_role.items()
        if role in source_roles
    }
    try:
        return replace_section_roles(source, replacements)
    except LasSectionEditError as exc:
        raise LasExportError(f"Lossless-экспорт секций невозможен: {exc}") from exc


def _adapt_generated_section(payload: bytes, source: LosslessLasDocument) -> bytes:
    text = payload.decode("utf-8")
    if source.newline_style is not NewlineStyle.MIXED:
        newline = {
            NewlineStyle.CRLF: "\r\n",
            NewlineStyle.CR: "\r",
            NewlineStyle.LF: "\n",
            NewlineStyle.NONE: "\n",
        }[source.newline_style]
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
    try:
        target_encoding = "utf-8" if source.encoding == "utf-8-sig" else source.encoding
        return text.encode(target_encoding)
    except UnicodeEncodeError as exc:
        raise LasExportError(
            f"Новые данные нельзя представить в исходной кодировке {source.encoding}"
        ) from exc


def _build_las_file(dataset: Dataset, *, null_value: float) -> lasio.LASFile:
    las = lasio.LASFile()
    active = dataset.active_index
    index_mnemonic = _las_index_mnemonic(dataset)
    index_unit = active.unit or ("s" if active.role is IndexRole.TIME else "m")
    index_description = "ELAPSED TIME" if active.role is IndexRole.TIME else "MEASURED DEPTH"
    las.append_curve(
        index_mnemonic,
        np.asarray(active.values, dtype=np.float64),
        unit=index_unit,
        descr=index_description,
    )
    for curve in dataset.curves.values():
        las.append_curve(
            curve.metadata.original_mnemonic.strip(),
            np.asarray(curve.values, dtype=np.float64),
            unit=curve.metadata.unit or "",
            descr=curve.metadata.description or "",
        )
    _apply_header_values(
        las.version,
        {
            key: value
            for key, value in dataset.version_headers.items()
            if key not in {"VERS", "WRAP"}
        },
    )
    _apply_header_values(las.well, dataset.headers)
    _apply_header_values(las.params, dataset.parameters)
    _apply_active_index_headers(las, active)
    las.well["NULL"].value = null_value
    return las



def _apply_active_index_headers(las: lasio.LASFile, index: DatasetIndex) -> None:
    values = np.asarray(index.values, dtype=np.float64)
    finite = values[np.isfinite(values)]
    if not finite.size:
        return
    las.well["STRT"].value = float(finite[0])
    las.well["STOP"].value = float(finite[-1])
    differences = np.diff(finite)
    positive = differences[differences > 0]
    if positive.size:
        nominal_step = float(np.median(positive))
    else:
        negative = differences[differences < 0]
        nominal_step = float(np.median(negative)) if negative.size else 0.0
    las.well["STEP"].value = nominal_step
    unit = index.unit or ("s" if index.role is IndexRole.TIME else "m")
    las.well["STRT"].unit = unit
    las.well["STOP"].unit = unit
    las.well["STEP"].unit = unit


def _las_index_mnemonic(dataset: Dataset) -> str:
    active = dataset.active_index
    if active.role is IndexRole.TIME:
        mnemonic = active.mnemonic.strip().upper()
        return mnemonic if mnemonic in {"TIME", "ETIME"} else "TIME"
    mnemonic = active.mnemonic.strip().upper()
    return mnemonic if mnemonic in {"DEPT", "DEPTH", "MD", "TVD", "TVDSS"} else "DEPT"

def _apply_header_values(section, values: dict[str, str]) -> None:
    for mnemonic, value in values.items():
        try:
            section[mnemonic].value = value
        except KeyError:
            section.append(lasio.HeaderItem(mnemonic, "", value, ""))


def _same_path(first: Path, second: Path) -> bool:
    return first.expanduser().resolve(strict=False) == second.expanduser().resolve(strict=False)
