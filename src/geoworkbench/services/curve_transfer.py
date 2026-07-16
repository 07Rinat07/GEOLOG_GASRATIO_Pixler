from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, IndexRole, new_id
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis


class CurveTransferMapping(StrEnum):
    EXACT = "exact"
    LINEAR = "linear"


@dataclass(frozen=True, slots=True)
class CurveTransferCandidate:
    curve_id: str
    mnemonic: str
    unit: str | None
    missing_count: int
    conflict: str | None = None


@dataclass(frozen=True, slots=True)
class CurveTransferAnalysis:
    source_dataset_id: str
    target_dataset_id: str
    mapping: CurveTransferMapping
    candidates: tuple[CurveTransferCandidate, ...]

    @property
    def transferable(self) -> tuple[CurveTransferCandidate, ...]:
        return tuple(candidate for candidate in self.candidates if candidate.conflict is None)


def analyze_curve_transfer(source: Dataset, target: Dataset) -> CurveTransferAnalysis:
    if source.dataset_id == target.dataset_id:
        raise ValueError("Источник и приёмник кривых должны быть разными dataset")
    _validate_depth_index(source, "Источник")
    _validate_depth_index(target, "Приёмник")
    source_unit = (source.active_index.unit or "").strip().casefold()
    target_unit = (target.active_index.unit or "").strip().casefold()
    if source_unit != target_unit:
        raise ValueError(
            "Единицы глубинных индексов не совпадают: "
            f"{source.active_index.unit or '—'} и {target.active_index.unit or '—'}"
        )
    if source.depth.shape == target.depth.shape and np.allclose(
        source.depth, target.depth, rtol=0.0, atol=_depth_tolerance(source, target)
    ):
        mapping = CurveTransferMapping.EXACT
    else:
        if target.depth[0] < source.depth[0] or target.depth[-1] > source.depth[-1]:
            raise ValueError(
                "Диапазон приёмника должен находиться внутри диапазона источника"
            )
        mapping = CurveTransferMapping.LINEAR
    target_mnemonics = {
        curve.metadata.original_mnemonic.casefold() for curve in target.curves.values()
    }
    index_mnemonics = {"dept"} | {
        index.mnemonic.casefold() for index in target.indexes.values()
    }
    invalid_shapes = [
        curve.metadata.original_mnemonic
        for curve in source.curves.values()
        if curve.values.shape != source.depth.shape
    ]
    if invalid_shapes:
        raise ValueError(
            "Размер кривых источника не совпадает с индексом: "
            + ", ".join(invalid_shapes)
        )
    candidates = tuple(
        CurveTransferCandidate(
            curve_id=curve.metadata.curve_id,
            mnemonic=curve.metadata.original_mnemonic,
            unit=curve.metadata.unit,
            missing_count=int(np.count_nonzero(~np.isfinite(curve.values))),
            conflict=(
                "Мнемоника занята кривой приёмника"
                if curve.metadata.original_mnemonic.casefold() in target_mnemonics
                else "Мнемоника зарезервирована индексом приёмника"
                if curve.metadata.original_mnemonic.casefold() in index_mnemonics
                else None
            ),
        )
        for curve in source.curves.values()
    )
    return CurveTransferAnalysis(
        source.dataset_id,
        target.dataset_id,
        mapping,
        candidates,
    )


def build_transferred_curves(
    source: Dataset,
    target: Dataset,
    curve_ids: tuple[str, ...],
    *,
    analysis: CurveTransferAnalysis | None = None,
) -> tuple[CurveData, ...]:
    current = analyze_curve_transfer(source, target)
    if analysis is not None and current != analysis:
        raise ValueError("Dataset изменился после анализа вставки кривых")
    selected = tuple(dict.fromkeys(curve_ids))
    if not selected:
        raise ValueError("Выберите хотя бы одну кривую для вставки")
    candidates = {candidate.curve_id: candidate for candidate in current.candidates}
    unknown = [curve_id for curve_id in selected if curve_id not in candidates]
    if unknown:
        raise KeyError("Кривые источника не найдены: " + ", ".join(unknown))
    conflicts = [
        candidates[curve_id].mnemonic
        for curve_id in selected
        if candidates[curve_id].conflict is not None
    ]
    if conflicts:
        raise ValueError("Конфликт мнемоник: " + ", ".join(conflicts))
    result: list[CurveData] = []
    for curve_id in selected:
        source_curve = source.curves[curve_id]
        values = (
            np.asarray(source_curve.values, dtype=np.float64).copy()
            if current.mapping is CurveTransferMapping.EXACT
            else _interpolate_without_bridging(
                source.depth,
                np.asarray(source_curve.values, dtype=np.float64),
                target.depth,
            )
        )
        metadata = source_curve.metadata
        new_curve_id = new_id()
        result.append(
            CurveData(
                CurveMetadata(
                    curve_id=new_curve_id,
                    original_mnemonic=metadata.original_mnemonic,
                    canonical_mnemonic=metadata.canonical_mnemonic,
                    unit=metadata.unit,
                    description=metadata.description,
                    source_dataset_id=target.dataset_id,
                    provenance=f"transfer:{source.dataset_id}:{curve_id}",
                ),
                values,
            )
        )
    return tuple(result)


def _validate_depth_index(dataset: Dataset, label: str) -> None:
    if dataset.active_index.role is not IndexRole.DEPTH:
        raise ValueError(f"{label} должен использовать активный глубинный индекс")
    report = analyze_depth_axis(dataset.depth)
    if (
        report.direction is not DepthDirection.ASCENDING
        or report.duplicate_count
        or report.missing_count
    ):
        raise ValueError(
            f"{label} должен иметь возрастающий индекс без пропусков и дубликатов"
        )


def _depth_tolerance(source: Dataset, target: Dataset) -> float:
    scale = max(
        1.0,
        float(np.max(np.abs(source.depth))),
        float(np.max(np.abs(target.depth))),
    )
    return np.finfo(np.float64).eps * scale * 16


def _interpolate_without_bridging(
    source_depth: NDArray[np.float64],
    source_values: NDArray[np.float64],
    target_depth: NDArray[np.float64],
) -> NDArray[np.float64]:
    result = np.full(target_depth.shape, np.nan, dtype=np.float64)
    right = np.searchsorted(source_depth, target_depth, side="left")
    tolerance = np.finfo(np.float64).eps * max(
        1.0, float(np.max(np.abs(source_depth)))
    ) * 16
    bounded_right = np.minimum(right, source_depth.size - 1)
    exact = (right < source_depth.size) & np.isclose(
        source_depth[bounded_right], target_depth, rtol=0.0, atol=tolerance
    )
    exact_positions = np.flatnonzero(exact)
    exact_source = right[exact_positions]
    valid_exact = np.isfinite(source_values[exact_source])
    result[exact_positions[valid_exact]] = source_values[exact_source[valid_exact]]
    between = np.flatnonzero(~exact & (right > 0) & (right < source_depth.size))
    left_source = right[between] - 1
    right_source = right[between]
    valid = np.isfinite(source_values[left_source]) & np.isfinite(
        source_values[right_source]
    )
    positions = between[valid]
    left_source = left_source[valid]
    right_source = right_source[valid]
    weight = (target_depth[positions] - source_depth[left_source]) / (
        source_depth[right_source] - source_depth[left_source]
    )
    result[positions] = source_values[left_source] + weight * (
        source_values[right_source] - source_values[left_source]
    )
    return result
