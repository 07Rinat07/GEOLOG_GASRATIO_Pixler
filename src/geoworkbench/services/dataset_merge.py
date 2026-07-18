from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    IndexRole,
    new_id,
)
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis


@dataclass(frozen=True, slots=True)
class DatasetMergeAnalysis:
    source_dataset_id: str
    target_dataset_id: str
    source_sample_count: int
    target_sample_count: int
    merged_sample_count: int
    overlap_sample_count: int
    mnemonic_conflicts: tuple[str, ...]

    @property
    def can_merge(self) -> bool:
        return not self.mnemonic_conflicts


def analyze_dataset_merge(source: Dataset, target: Dataset) -> DatasetMergeAnalysis:
    _validate_pair(source, target)
    merged_depth = _union_depth(source.depth, target.depth)
    overlap = source.depth.size + target.depth.size - merged_depth.size
    target_mnemonics = {
        curve.metadata.original_mnemonic.casefold(): curve.metadata.original_mnemonic
        for curve in target.curves.values()
    }
    conflicts = sorted(
        {
            target_mnemonics[curve.metadata.original_mnemonic.casefold()]
            for curve in source.curves.values()
            if curve.metadata.original_mnemonic.casefold() in target_mnemonics
        },
        key=str.casefold,
    )
    return DatasetMergeAnalysis(
        source.dataset_id,
        target.dataset_id,
        int(source.depth.size),
        int(target.depth.size),
        int(merged_depth.size),
        int(overlap),
        tuple(conflicts),
    )


def create_merged_dataset(
    source: Dataset,
    target: Dataset,
    analysis: DatasetMergeAnalysis,
    *,
    name: str | None = None,
) -> Dataset:
    current = analyze_dataset_merge(source, target)
    if current != analysis:
        raise ValueError("Dataset изменился после анализа сращивания")
    if not current.can_merge:
        raise ValueError(
            "Конфликт мнемоник при сращивании: "
            + ", ".join(current.mnemonic_conflicts)
        )
    merged_depth = _union_depth(source.depth, target.depth)
    dataset_id = new_id()
    index_id = f"{dataset_id}:primary-index"
    target_index = target.active_index
    result = Dataset(
        dataset_id=dataset_id,
        name=name or f"{target.name} + {source.name}",
        kind=DatasetKind.DERIVED,
        depth_domain=target.depth_domain,
        depth=merged_depth,
        source_path=None,
        headers=dict(target.headers),
        parameters=dict(target.parameters),
        indexes={
            index_id: DatasetIndex(
                index_id=index_id,
                mnemonic=target_index.mnemonic,
                index_type=target_index.index_type,
                role=IndexRole.DEPTH,
                unit=target_index.unit,
                values=merged_depth,
                evidence=(
                    f"merge-target:{target.dataset_id}",
                    f"merge-source:{source.dataset_id}",
                ),
            )
        },
        active_index_id=index_id,
        version_headers=dict(target.version_headers),
    )
    for owner, dataset in (("target", target), ("source", source)):
        positions = _positions_on_union(dataset.depth, merged_depth)
        for curve in dataset.curves.values():
            if curve.values.shape != dataset.depth.shape:
                raise ValueError(
                    f"Размер кривой {curve.metadata.original_mnemonic} не совпадает с индексом"
                )
            values = np.full(merged_depth.shape, np.nan, dtype=np.float64)
            values[positions] = curve.values
            metadata = curve.metadata
            curve_id = new_id()
            result.curves[curve_id] = CurveData(
                CurveMetadata(
                    curve_id=curve_id,
                    original_mnemonic=metadata.original_mnemonic,
                    canonical_mnemonic=metadata.canonical_mnemonic,
                    unit=metadata.unit,
                    description=metadata.description,
                    source_dataset_id=dataset_id,
                    provenance=f"merge:{owner}:{dataset.dataset_id}:{metadata.curve_id}",
                ),
                values,
            )
    merged_report = analyze_depth_axis(merged_depth)
    result.headers.update(
        {
            "STRT": f"{merged_depth[0]:.15g}",
            "STOP": f"{merged_depth[-1]:.15g}",
            "STEP": (
                f"{merged_report.nominal_step:.15g}"
                if merged_report.is_uniform and merged_report.nominal_step is not None
                else ""
            ),
        }
    )
    return result


def _validate_pair(source: Dataset, target: Dataset) -> None:
    if source.dataset_id == target.dataset_id:
        raise ValueError("Источник и приёмник должны быть разными dataset")
    for label, dataset in (("Источник", source), ("Приёмник", target)):
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
        if len(dataset.indexes) != 1:
            raise ValueError(
                f"{label} содержит дополнительные индексы; безопасная стратегия не выбрана"
            )
    if source.active_index.index_type is not target.active_index.index_type:
        raise ValueError("Типы глубинных индексов не совпадают")
    source_unit = (source.active_index.unit or "").strip().casefold()
    target_unit = (target.active_index.unit or "").strip().casefold()
    if source_unit != target_unit:
        raise ValueError("Единицы глубинных индексов не совпадают")


def _union_depth(
    source_depth: NDArray[np.float64], target_depth: NDArray[np.float64]
) -> NDArray[np.float64]:
    values = np.concatenate((target_depth, source_depth))
    priorities = np.concatenate(
        (
            np.zeros(target_depth.size, dtype=np.int8),
            np.ones(source_depth.size, dtype=np.int8),
        )
    )
    order = np.lexsort((priorities, values))
    sorted_values = values[order]
    sorted_priorities = priorities[order]
    tolerance = _tolerance(values)
    representatives: list[float] = []
    start = 0
    while start < sorted_values.size:
        stop = start + 1
        while (
            stop < sorted_values.size
            and sorted_values[stop] - sorted_values[stop - 1] <= tolerance
        ):
            stop += 1
        group_values = sorted_values[start:stop]
        group_priorities = sorted_priorities[start:stop]
        target_positions = np.flatnonzero(group_priorities == 0)
        chosen = int(target_positions[0]) if target_positions.size else 0
        representatives.append(float(group_values[chosen]))
        start = stop
    return np.asarray(representatives, dtype=np.float64)


def _positions_on_union(
    depth: NDArray[np.float64], merged_depth: NDArray[np.float64]
) -> NDArray[np.int64]:
    right = np.searchsorted(merged_depth, depth)
    right = np.minimum(right, merged_depth.size - 1)
    left = np.maximum(right - 1, 0)
    choose_left = np.abs(merged_depth[left] - depth) <= np.abs(
        merged_depth[right] - depth
    )
    positions = np.where(choose_left, left, right).astype(np.int64)
    if np.any(np.abs(merged_depth[positions] - depth) > _tolerance(merged_depth)):
        raise RuntimeError("Не удалось сопоставить глубину с объединённой сеткой")
    return positions


def _tolerance(values: NDArray[np.float64]) -> float:
    return np.finfo(np.float64).eps * max(1.0, float(np.max(np.abs(values)))) * 16
