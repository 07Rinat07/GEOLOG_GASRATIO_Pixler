from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from geoworkbench.data.las_adapter import LasImportResult
from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, IndexRole, new_id
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis, create_ascending_depth_copy


class ExternalLasMapping(StrEnum):
    EXACT = "exact"
    LINEAR_OVERLAP = "linear_overlap"


@dataclass(frozen=True, slots=True)
class ExternalLasCurveCandidate:
    source_curve_id: str
    source_mnemonic: str
    source_unit: str | None
    source_description: str | None
    suggested_mnemonic: str
    finite_count: int
    missing_count: int


@dataclass(frozen=True, slots=True)
class ExternalLasInsertAnalysis:
    source_path: Path
    source_dataset_id: str
    target_dataset_id: str
    source_sha256: str
    source_encoding: str
    source_original_direction: DepthDirection
    source_reversed_in_memory: bool
    source_depth_unit: str
    target_depth_unit: str
    depth_conversion_factor: float
    source_depth_min: float
    source_depth_max: float
    target_depth_min: float
    target_depth_max: float
    overlap_top: float
    overlap_bottom: float
    mapping: ExternalLasMapping
    candidates: tuple[ExternalLasCurveCandidate, ...]

    @property
    def overlap_span(self) -> float:
        return self.overlap_bottom - self.overlap_top


@dataclass(frozen=True, slots=True)
class ExternalLasCurveSelection:
    source_curve_id: str
    target_mnemonic: str
    display_name: str = ""


@dataclass(frozen=True, slots=True)
class ExternalLasInsertBuild:
    curves: tuple[CurveData, ...]
    manifest_json: str


def analyze_external_las_insert(
    imported: LasImportResult,
    target: Dataset,
) -> tuple[ExternalLasInsertAnalysis, Dataset]:
    """Analyze direct insertion of curves from an external LAS into a target dataset.

    The source file itself is never modified. A descending source is reversed only in
    memory before mapping. The target remains unchanged until the controller applies a
    validated selection.
    """

    source_original = imported.dataset
    source_report = analyze_depth_axis(source_original.depth)
    if source_report.direction is DepthDirection.DESCENDING:
        source = create_ascending_depth_copy(
            source_original,
            name=f"{source_original.name} — temporary ascending source",
        )
        source_reversed = True
    elif source_report.direction is DepthDirection.ASCENDING:
        source = source_original
        source_reversed = False
    else:
        raise ValueError(
            "Внешний LAS должен иметь монотонный глубинный индекс; "
            f"получено направление {source_report.direction.value}"
        )

    _validate_depth_dataset(source, "Внешний LAS")
    _validate_depth_dataset(target, "Текущий LAS")

    source_unit = _normalize_depth_unit(source.active_index.unit)
    target_unit = _normalize_depth_unit(target.active_index.unit)
    factor = _depth_factor(source_unit, target_unit)
    source_depth = np.asarray(source.depth, dtype=np.float64) * factor
    target_depth = np.asarray(target.depth, dtype=np.float64)

    overlap_top = max(float(source_depth[0]), float(target_depth[0]))
    overlap_bottom = min(float(source_depth[-1]), float(target_depth[-1]))
    if overlap_bottom < overlap_top or np.isclose(overlap_bottom, overlap_top):
        raise ValueError(
            "Диапазоны глубины внешнего и текущего LAS не пересекаются: "
            f"{source_depth[0]:g}–{source_depth[-1]:g} {target_unit} и "
            f"{target_depth[0]:g}–{target_depth[-1]:g} {target_unit}"
        )

    tolerance = _depth_tolerance(source_depth, target_depth)
    mapping = (
        ExternalLasMapping.EXACT
        if source_depth.shape == target_depth.shape
        and np.allclose(source_depth, target_depth, rtol=0.0, atol=tolerance)
        else ExternalLasMapping.LINEAR_OVERLAP
    )
    occupied = {
        curve.metadata.original_mnemonic.strip().casefold() for curve in target.curves.values()
    }
    occupied.update(index.mnemonic.strip().casefold() for index in target.indexes.values())
    source_tag = _mnemonic_tag(imported.dataset.name)
    candidates: list[ExternalLasCurveCandidate] = []
    for curve in source.curves.values():
        values = np.asarray(curve.values, dtype=np.float64)
        suggested = _unique_mnemonic(curve.metadata.original_mnemonic, occupied, source_tag)
        occupied.add(suggested.casefold())
        candidates.append(
            ExternalLasCurveCandidate(
                source_curve_id=curve.metadata.curve_id,
                source_mnemonic=curve.metadata.original_mnemonic,
                source_unit=curve.metadata.unit,
                source_description=curve.metadata.description,
                suggested_mnemonic=suggested,
                finite_count=int(np.count_nonzero(np.isfinite(values))),
                missing_count=int(np.count_nonzero(~np.isfinite(values))),
            )
        )

    analysis = ExternalLasInsertAnalysis(
        source_path=imported.report.source.path,
        source_dataset_id=source.dataset_id,
        target_dataset_id=target.dataset_id,
        source_sha256=imported.report.source.sha256,
        source_encoding=imported.report.source.encoding,
        source_original_direction=source_report.direction,
        source_reversed_in_memory=source_reversed,
        source_depth_unit=source_unit,
        target_depth_unit=target_unit,
        depth_conversion_factor=factor,
        source_depth_min=float(source_depth[0]),
        source_depth_max=float(source_depth[-1]),
        target_depth_min=float(target_depth[0]),
        target_depth_max=float(target_depth[-1]),
        overlap_top=overlap_top,
        overlap_bottom=overlap_bottom,
        mapping=mapping,
        candidates=tuple(candidates),
    )
    return analysis, source


def build_external_las_curves(
    source: Dataset,
    target: Dataset,
    analysis: ExternalLasInsertAnalysis,
    selections: tuple[ExternalLasCurveSelection, ...],
) -> ExternalLasInsertBuild:
    if target.dataset_id != analysis.target_dataset_id:
        raise ValueError("Текущий LAS изменился после анализа вставки")
    if source.dataset_id != analysis.source_dataset_id:
        raise ValueError("Внешний LAS изменился после анализа вставки")
    if not selections:
        raise ValueError("Выберите хотя бы одну кривую для вставки")

    source_by_id = source.curves
    selected_ids = [item.source_curve_id for item in selections]
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("Одна исходная кривая выбрана несколько раз")
    missing = [curve_id for curve_id in selected_ids if curve_id not in source_by_id]
    if missing:
        raise KeyError("Кривые внешнего LAS не найдены: " + ", ".join(missing))

    reserved = {index.mnemonic.strip().casefold() for index in target.indexes.values()}
    reserved.update(curve.metadata.original_mnemonic.strip().casefold() for curve in target.curves.values())
    normalized_names: list[str] = []
    for selection in selections:
        mnemonic = _validate_output_mnemonic(selection.target_mnemonic)
        folded = mnemonic.casefold()
        if folded in reserved or folded in {item.casefold() for item in normalized_names}:
            raise ValueError(f"Мнемоника уже занята в текущем LAS: {mnemonic}")
        normalized_names.append(mnemonic)

    source_depth = np.asarray(source.depth, dtype=np.float64) * analysis.depth_conversion_factor
    target_depth = np.asarray(target.depth, dtype=np.float64)
    curves: list[CurveData] = []
    manifest_curves: list[dict[str, object]] = []
    for selection, target_mnemonic in zip(selections, normalized_names, strict=True):
        source_curve = source_by_id[selection.source_curve_id]
        source_values = np.asarray(source_curve.values, dtype=np.float64)
        values = (
            source_values.copy()
            if analysis.mapping is ExternalLasMapping.EXACT
            else _interpolate_without_bridging(source_depth, source_values, target_depth)
        )
        curve_id = new_id()
        source_metadata = source_curve.metadata
        display_name = selection.display_name.strip()
        description = display_name or source_metadata.description
        provenance = (
            f"external-las:{analysis.source_sha256}:"
            f"{source_metadata.original_mnemonic}:{source_metadata.unit or ''}"
        )
        curves.append(
            CurveData(
                CurveMetadata(
                    curve_id=curve_id,
                    original_mnemonic=target_mnemonic,
                    canonical_mnemonic=source_metadata.canonical_mnemonic,
                    unit=source_metadata.unit,
                    description=description,
                    source_dataset_id=target.dataset_id,
                    provenance=provenance,
                ),
                values,
            )
        )
        manifest_curves.append(
            {
                "source_curve_id": source_metadata.curve_id,
                "source_mnemonic": source_metadata.original_mnemonic,
                "source_unit": source_metadata.unit,
                "target_curve_id": curve_id,
                "target_mnemonic": target_mnemonic,
                "display_name": description or "",
                "finite_count": int(np.count_nonzero(np.isfinite(values))),
            }
        )

    manifest = {
        "version": 1,
        "source_path": str(analysis.source_path),
        "source_sha256": analysis.source_sha256,
        "source_encoding": analysis.source_encoding,
        "source_original_direction": analysis.source_original_direction.value,
        "source_reversed_in_memory": analysis.source_reversed_in_memory,
        "source_depth_unit": analysis.source_depth_unit,
        "target_depth_unit": analysis.target_depth_unit,
        "depth_conversion_factor": analysis.depth_conversion_factor,
        "mapping": analysis.mapping.value,
        "overlap": [analysis.overlap_top, analysis.overlap_bottom],
        "curves": manifest_curves,
    }
    return ExternalLasInsertBuild(
        curves=tuple(curves),
        manifest_json=json.dumps(manifest, ensure_ascii=False, sort_keys=True),
    )


def _validate_depth_dataset(dataset: Dataset, label: str) -> None:
    if dataset.active_index.role is not IndexRole.DEPTH:
        raise ValueError(f"{label} должен использовать глубинный индекс")
    report = analyze_depth_axis(dataset.depth)
    if (
        report.direction is not DepthDirection.ASCENDING
        or report.duplicate_count
        or report.missing_count
    ):
        raise ValueError(
            f"{label} должен иметь возрастающий индекс без пропусков и дубликатов"
        )


def _normalize_depth_unit(unit: str | None) -> str:
    normalized = (unit or "m").strip().casefold().replace(".", "")
    aliases = {
        "m": "m",
        "meter": "m",
        "meters": "m",
        "metre": "m",
        "metres": "m",
        "м": "m",
        "метр": "m",
        "метры": "m",
        "ft": "ft",
        "feet": "ft",
        "foot": "ft",
        "фут": "ft",
        "футы": "ft",
        "cm": "cm",
        "см": "cm",
        "mm": "mm",
        "мм": "mm",
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"Неподдерживаемая единица глубины: {unit or '—'}") from exc


def _depth_factor(source_unit: str, target_unit: str) -> float:
    metres = {"m": 1.0, "ft": 0.3048, "cm": 0.01, "mm": 0.001}
    return metres[source_unit] / metres[target_unit]


def _depth_tolerance(first: NDArray[np.float64], second: NDArray[np.float64]) -> float:
    scale = max(1.0, float(np.max(np.abs(first))), float(np.max(np.abs(second))))
    return float(np.finfo(np.float64).eps * scale * 32)


def _interpolate_without_bridging(
    source_depth: NDArray[np.float64],
    source_values: NDArray[np.float64],
    target_depth: NDArray[np.float64],
) -> NDArray[np.float64]:
    result = np.full(target_depth.shape, np.nan, dtype=np.float64)
    if source_depth.size == 0:
        return result
    tolerance = _depth_tolerance(source_depth, target_depth)
    right = np.searchsorted(source_depth, target_depth, side="left")
    bounded = np.minimum(right, source_depth.size - 1)
    exact = (right < source_depth.size) & np.isclose(
        source_depth[bounded], target_depth, rtol=0.0, atol=tolerance
    )
    exact_positions = np.flatnonzero(exact)
    exact_source = right[exact_positions]
    usable_exact = np.isfinite(source_values[exact_source])
    result[exact_positions[usable_exact]] = source_values[exact_source[usable_exact]]

    between = np.flatnonzero(~exact & (right > 0) & (right < source_depth.size))
    if between.size == 0:
        return result
    left_source = right[between] - 1
    right_source = right[between]
    step_report = analyze_depth_axis(source_depth)
    maximum_bridge = (
        step_report.nominal_step * 1.5 + tolerance
        if step_report.nominal_step is not None
        else np.inf
    )
    gaps = source_depth[right_source] - source_depth[left_source]
    usable = (
        np.isfinite(source_values[left_source])
        & np.isfinite(source_values[right_source])
        & (gaps <= maximum_bridge)
    )
    positions = between[usable]
    left_source = left_source[usable]
    right_source = right_source[usable]
    weight = (target_depth[positions] - source_depth[left_source]) / (
        source_depth[right_source] - source_depth[left_source]
    )
    result[positions] = source_values[left_source] + weight * (
        source_values[right_source] - source_values[left_source]
    )
    return result


_CYRILLIC_TRANSLITERATION = str.maketrans(
    {
        "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E",
        "Ё": "E", "Ж": "ZH", "З": "Z", "И": "I", "Й": "I", "К": "K",
        "Л": "L", "М": "M", "Н": "N", "О": "O", "П": "P", "Р": "R",
        "С": "S", "Т": "T", "У": "U", "Ф": "F", "Х": "H", "Ц": "TS",
        "Ч": "CH", "Ш": "SH", "Щ": "SCH", "Ъ": "", "Ы": "Y", "Ь": "",
        "Э": "E", "Ю": "YU", "Я": "YA",
        "Ә": "A", "Ғ": "G", "Қ": "K", "Ң": "N", "Ө": "O", "Ұ": "U",
        "Ү": "U", "Һ": "H", "І": "I",
    }
)


def sanitize_las_mnemonic(value: str, *, fallback: str = "CURVE") -> str:
    """Return a deterministic LAS-safe mnemonic without changing source metadata.

    Vendor LAS files often contain duplicate names exposed by ``lasio`` as
    ``GK:1``/``GK:2`` or Cyrillic labels such as ``КС, ННК/ДСР``.  Those names
    remain visible as the source mnemonic, while the output copy receives a
    portable ASCII mnemonic such as ``GK_1`` or ``KS_NNK_DSR``.
    """

    text = value.strip().upper().translate(_CYRILLIC_TRANSLITERATION)
    text = re.sub(r"[^A-Z0-9_.$-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_.-$")
    if not text:
        text = fallback.strip().upper() or "CURVE"
    return text[:64]


def _validate_output_mnemonic(value: str) -> str:
    mnemonic = value.strip().upper().replace(" ", "_")
    if not mnemonic:
        raise ValueError("Выходная мнемоника не может быть пустой")
    if len(mnemonic) > 64:
        raise ValueError("Выходная мнемоника не должна превышать 64 символа")
    if not re.fullmatch(r"[A-Z0-9_.$-]+", mnemonic):
        raise ValueError(
            "Выходная мнемоника может содержать латинские буквы, цифры, _, -, . и $"
        )
    return mnemonic


def _mnemonic_tag(value: str) -> str:
    return sanitize_las_mnemonic(value, fallback="EXT")[:12]


def _unique_mnemonic(base: str, occupied: set[str], source_tag: str) -> str:
    normalized = sanitize_las_mnemonic(base)
    if normalized.casefold() not in occupied:
        return normalized
    tagged = f"{normalized}_{source_tag}"
    if tagged.casefold() not in occupied:
        return tagged
    suffix = 2
    while f"{tagged}_{suffix}".casefold() in occupied:
        suffix += 1
    return f"{tagged}_{suffix}"
