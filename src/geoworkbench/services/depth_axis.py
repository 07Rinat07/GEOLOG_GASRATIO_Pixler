from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import floor, isfinite
from typing import Any

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    new_id,
)

MAX_DEPTH_GRID_SAMPLES = 5_000_000


class DepthDirection(StrEnum):
    ASCENDING = "ascending"
    DESCENDING = "descending"
    MIXED = "mixed"
    CONSTANT = "constant"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DepthAxisReport:
    direction: DepthDirection
    start: float | None
    stop: float | None
    nominal_step: float | None
    is_uniform: bool
    duplicate_count: int
    missing_count: int
    gap_count: int


@dataclass(frozen=True, slots=True)
class DepthResamplePlan:
    start: float
    stop: float
    step: float
    source_sample_count: int
    target_sample_count: int
    curve_count: int
    index_count: int


def analyze_depth_axis(values: NDArray[np.float64]) -> DepthAxisReport:
    depth = np.asarray(values, dtype=np.float64)
    if depth.ndim != 1:
        raise ValueError("Шкала глубины должна быть одномерной")
    finite_mask = np.isfinite(depth)
    finite = depth[finite_mask]
    missing_count = int(depth.size - finite.size)
    if finite.size == 0:
        return DepthAxisReport(DepthDirection.UNKNOWN, None, None, None, False, 0, missing_count, 0)
    if finite.size == 1:
        value = float(finite[0])
        return DepthAxisReport(
            DepthDirection.UNKNOWN, value, value, None, True, 0, missing_count, 0
        )

    differences = np.diff(finite)
    scale = max(1.0, float(np.max(np.abs(finite))))
    absolute_tolerance = np.finfo(np.float64).eps * scale * 16
    zero = np.isclose(differences, 0.0, rtol=0.0, atol=absolute_tolerance)
    positive = differences > absolute_tolerance
    negative = differences < -absolute_tolerance
    duplicate_count = int(np.count_nonzero(zero))

    if np.all(zero):
        direction = DepthDirection.CONSTANT
    elif np.all(positive | zero) and np.any(positive):
        direction = DepthDirection.ASCENDING
    elif np.all(negative | zero) and np.any(negative):
        direction = DepthDirection.DESCENDING
    else:
        direction = DepthDirection.MIXED

    nonzero_steps = np.abs(differences[~zero])
    nominal_step = float(np.median(nonzero_steps)) if nonzero_steps.size else None
    is_uniform = bool(
        nominal_step is not None
        and np.allclose(nonzero_steps, nominal_step, rtol=1e-6, atol=absolute_tolerance)
    )
    gap_count = (
        int(np.count_nonzero(nonzero_steps > nominal_step * 1.5)) if nominal_step is not None else 0
    )
    return DepthAxisReport(
        direction=direction,
        start=float(finite[0]),
        stop=float(finite[-1]),
        nominal_step=nominal_step,
        is_uniform=is_uniform,
        duplicate_count=duplicate_count,
        missing_count=missing_count,
        gap_count=gap_count,
    )


def build_depth_grid(start: float, stop: float, step: float) -> NDArray[np.float64]:
    if not all(isfinite(value) for value in (start, stop, step)):
        raise ValueError("Границы и шаг глубины должны быть конечными")
    if start >= stop:
        raise ValueError("Начальная глубина должна быть меньше конечной")
    if step <= 0:
        raise ValueError("Шаг глубины должен быть положительным")
    count = floor((stop - start) / step + 1e-10) + 1
    if count > MAX_DEPTH_GRID_SAMPLES:
        raise ValueError(
            f"Новая сетка превышает безопасный предел {MAX_DEPTH_GRID_SAMPLES} отсчётов"
        )
    return start + np.arange(count, dtype=np.float64) * step


def analyze_depth_resample(
    dataset: Dataset, start: float, stop: float, step: float
) -> DepthResamplePlan:
    report = analyze_depth_axis(dataset.depth)
    if report.direction is not DepthDirection.ASCENDING or report.duplicate_count:
        raise ValueError("Ресэмплинг требует возрастающего индекса без пропусков и дубликатов")
    if report.missing_count:
        raise ValueError("Ресэмплинг требует возрастающего индекса без пропусков и дубликатов")
    grid = build_depth_grid(start, stop, step)
    if start < dataset.depth[0] or stop > dataset.depth[-1]:
        raise ValueError("Новая сетка должна находиться внутри исходного диапазона")
    for index in dataset.indexes.values():
        values = np.asarray(index.values)
        if index.index_id != dataset.active_index_id and not (
            np.issubdtype(values.dtype, np.number) or np.issubdtype(values.dtype, np.datetime64)
        ):
            raise ValueError(f"Индекс {index.mnemonic} нельзя безопасно интерполировать")
    return DepthResamplePlan(
        start=start,
        stop=stop,
        step=step,
        source_sample_count=int(dataset.depth.size),
        target_sample_count=int(grid.size),
        curve_count=len(dataset.curves),
        index_count=len(dataset.indexes),
    )


def create_resampled_depth_copy(
    dataset: Dataset,
    plan: DepthResamplePlan,
    *,
    name: str | None = None,
) -> Dataset:
    current = analyze_depth_resample(dataset, plan.start, plan.stop, plan.step)
    if current != plan:
        raise ValueError("Dataset изменился после анализа ресэмплинга")
    target_depth = build_depth_grid(plan.start, plan.stop, plan.step)
    dataset_id = new_id()
    index_ids = {
        old_id: f"{dataset_id}:index:{position}"
        for position, old_id in enumerate(dataset.indexes, start=1)
    }
    indexes: dict[str, DatasetIndex] = {}
    for old_id, index in dataset.indexes.items():
        if old_id == dataset.active_index_id:
            values: np.ndarray[Any, np.dtype[Any]] = target_depth.copy()
        else:
            raw = np.asarray(index.values)
            if np.issubdtype(raw.dtype, np.datetime64):
                valid = ~np.isnat(raw)
                numeric = raw.astype("datetime64[ns]").astype(np.int64).astype(np.float64)
                interpolated = _interpolate_without_bridging(
                    dataset.depth, numeric, target_depth, valid
                )
                finite = np.isfinite(interpolated)
                values = np.full(interpolated.shape, np.datetime64("NaT"), dtype="datetime64[ns]")
                values[finite] = (
                    np.rint(interpolated[finite]).astype(np.int64).astype("datetime64[ns]")
                )
            else:
                numeric = np.asarray(raw, dtype=np.float64)
                values = _interpolate_without_bridging(
                    dataset.depth, numeric, target_depth, np.isfinite(numeric)
                )
        new_id_value = index_ids[old_id]
        indexes[new_id_value] = DatasetIndex(
            index_id=new_id_value,
            mnemonic=index.mnemonic,
            index_type=index.index_type,
            role=index.role,
            unit=index.unit,
            values=values,
            confidence=index.confidence,
            evidence=index.evidence + (f"resample-depth:{dataset.dataset_id}",),
            datetime_format=index.datetime_format,
            timezone=index.timezone,
        )
    result = Dataset(
        dataset_id=dataset_id,
        name=name or f"{dataset.name} — шаг {plan.step:g}",
        kind=DatasetKind.DERIVED,
        depth_domain=dataset.depth_domain,
        depth=target_depth,
        source_path=dataset.source_path,
        headers=dict(dataset.headers),
        parameters=dict(dataset.parameters),
        indexes=indexes,
        active_index_id=index_ids[dataset.active_index_id],  # type: ignore[index]
    )
    for curve in dataset.curves.values():
        metadata = curve.metadata
        curve_id = new_id()
        provenance = (
            metadata.provenance
            if metadata.provenance.startswith("calculation:")
            else f"transform:resample-depth:{dataset.dataset_id}"
        )
        result.curves[curve_id] = CurveData(
            CurveMetadata(
                curve_id=curve_id,
                original_mnemonic=metadata.original_mnemonic,
                canonical_mnemonic=metadata.canonical_mnemonic,
                unit=metadata.unit,
                description=metadata.description,
                source_dataset_id=dataset_id,
                provenance=provenance,
            ),
            _interpolate_without_bridging(
                dataset.depth,
                curve.values,
                target_depth,
                np.isfinite(curve.values),
            ),
        )
    result.headers.update(
        {"STRT": f"{plan.start:g}", "STOP": f"{target_depth[-1]:g}", "STEP": f"{plan.step:g}"}
    )
    return result


def _interpolate_without_bridging(
    source_depth: NDArray[np.float64],
    source_values: NDArray[np.float64],
    target_depth: NDArray[np.float64],
    valid: NDArray[np.bool_],
) -> NDArray[np.float64]:
    result = np.full(target_depth.shape, np.nan, dtype=np.float64)
    right = np.searchsorted(source_depth, target_depth, side="left")
    exact = (right < source_depth.size) & np.isclose(
        source_depth[np.minimum(right, source_depth.size - 1)], target_depth, rtol=0.0, atol=1e-12
    )
    exact_positions = np.flatnonzero(exact)
    exact_source = right[exact_positions]
    usable_exact = valid[exact_source]
    result[exact_positions[usable_exact]] = source_values[exact_source[usable_exact]]
    between = np.flatnonzero(~exact & (right > 0) & (right < source_depth.size))
    left_source = right[between] - 1
    right_source = right[between]
    usable = valid[left_source] & valid[right_source]
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


def create_ascending_depth_copy(dataset: Dataset, *, name: str | None = None) -> Dataset:
    report = analyze_depth_axis(dataset.depth)
    if report.direction is not DepthDirection.DESCENDING:
        raise ValueError("Автоматический разворот доступен только для убывающей глубины")
    dataset_id = new_id()
    index_ids = {
        old_id: f"{dataset_id}:index:{position}"
        for position, old_id in enumerate(dataset.indexes, start=1)
    }
    indexes = {
        index_ids[old_id]: DatasetIndex(
            index_id=index_ids[old_id],
            mnemonic=index.mnemonic,
            index_type=index.index_type,
            role=index.role,
            unit=index.unit,
            values=np.asarray(index.values[::-1]).copy(),
            confidence=index.confidence,
            evidence=index.evidence + (f"reverse-depth:{dataset.dataset_id}",),
            datetime_format=index.datetime_format,
            timezone=index.timezone,
        )
        for old_id, index in dataset.indexes.items()
    }
    result = Dataset(
        dataset_id=dataset_id,
        name=name or f"{dataset.name} — глубина по возрастанию",
        kind=DatasetKind.DERIVED,
        depth_domain=dataset.depth_domain,
        depth=np.asarray(dataset.depth[::-1], dtype=np.float64).copy(),
        source_path=dataset.source_path,
        headers=dict(dataset.headers),
        parameters=dict(dataset.parameters),
        indexes=indexes,
        active_index_id=index_ids[dataset.active_index_id],  # type: ignore[index]
    )
    for curve in dataset.curves.values():
        metadata = curve.metadata
        new_curve_id = new_id()
        result.curves[new_curve_id] = CurveData(
            CurveMetadata(
                curve_id=new_curve_id,
                original_mnemonic=metadata.original_mnemonic,
                canonical_mnemonic=metadata.canonical_mnemonic,
                unit=metadata.unit,
                description=metadata.description,
                source_dataset_id=dataset_id,
                provenance=f"transform:reverse-depth:{dataset.dataset_id}",
            ),
            np.asarray(curve.values[::-1], dtype=np.float64).copy(),
        )
    result.headers.update(
        {
            "STRT": f"{result.depth[0]:g}",
            "STOP": f"{result.depth[-1]:g}",
            "STEP": f"{report.nominal_step:g}" if report.nominal_step is not None else "",
        }
    )
    return result
