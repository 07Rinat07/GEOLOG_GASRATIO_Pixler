from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

import numpy as np

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


class DepthAggregationMethod(StrEnum):
    FIRST = "first"
    LAST = "last"
    MEAN = "mean"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"
    NEAREST = "nearest"
    LINEAR = "linear"


@dataclass(frozen=True, slots=True)
class TimeToDepthPlan:
    source_dataset_id: str
    depth_index_id: str
    time_index_id: str | None
    start_depth: float
    stop_depth: float
    step: float
    method: DepthAggregationMethod = DepthAggregationMethod.MEAN

    def __post_init__(self) -> None:
        if not self.source_dataset_id.strip() or not self.depth_index_id.strip():
            raise ValueError("Dataset и DEPTH индекс должны быть указаны")
        for label, value in (
            ("начальная глубина", self.start_depth),
            ("конечная глубина", self.stop_depth),
            ("шаг", self.step),
        ):
            if not isfinite(float(value)):
                raise ValueError(f"{label} должна быть конечным числом")
        if self.stop_depth < self.start_depth:
            raise ValueError("Конечная глубина не может быть меньше начальной")
        if self.step <= 0:
            raise ValueError("Шаг глубины должен быть положительным")
        count = int(np.floor((self.stop_depth - self.start_depth) / self.step + 1e-12)) + 1
        if count > 5_000_000:
            raise ValueError("Результат превышает безопасный предел 5 000 000 строк")


@dataclass(frozen=True, slots=True)
class TimeToDepthResult:
    dataset: Dataset
    rows_per_bin: tuple[int, ...]
    empty_bin_count: int


def convert_time_dataset_to_depth(dataset: Dataset, plan: TimeToDepthPlan) -> TimeToDepthResult:
    if plan.source_dataset_id != dataset.dataset_id:
        raise ValueError("План относится к другому набору данных")
    depth_index = dataset.indexes.get(plan.depth_index_id)
    if depth_index is None or depth_index.role is not IndexRole.DEPTH:
        raise ValueError("Выбранный индекс не является глубинным")
    time_index = dataset.indexes.get(plan.time_index_id) if plan.time_index_id else None
    if time_index is not None and time_index.role is not IndexRole.TIME:
        raise ValueError("Выбранный TIME индекс имеет другую роль")

    source_depth = np.asarray(depth_index.values, dtype=np.float64)
    target_depth = _target_axis(plan.start_depth, plan.stop_depth, plan.step)
    groups = _depth_groups(source_depth, target_depth, plan.step)
    dataset_id = new_id()
    depth_id = f"{dataset_id}:index:depth"
    indexes: dict[str, DatasetIndex] = {
        depth_id: DatasetIndex(
            depth_id,
            "DEPT",
            IndexType.MD,
            IndexRole.DEPTH,
            depth_index.unit or "m",
            target_depth,
            confidence=1.0,
            evidence=depth_index.evidence
            + (
                f"time-to-depth:{dataset.dataset_id}",
                f"method:{plan.method.value}",
                f"step:{plan.step:g}",
            ),
        )
    }
    if time_index is not None:
        time_values = _aggregate_time_index(time_index, groups, source_depth, target_depth)
        time_id = f"{dataset_id}:index:time"
        indexes[time_id] = DatasetIndex(
            time_id,
            time_index.mnemonic,
            time_index.index_type,
            IndexRole.TIME,
            time_index.unit,
            time_values,
            confidence=time_index.confidence,
            evidence=time_index.evidence + (f"time-to-depth:{dataset.dataset_id}",),
            datetime_format=time_index.datetime_format,
            timezone=time_index.timezone,
        )

    result = Dataset(
        dataset_id=dataset_id,
        name=f"{dataset.name} — DEPTH {plan.step:g}",
        kind=DatasetKind.DERIVED,
        depth_domain=DepthDomain.MD,
        depth=target_depth,
        source_path=None,
        headers={
            **dataset.headers,
            "STRT": f"{target_depth[0]:g}",
            "STOP": f"{target_depth[-1]:g}",
            "STEP": f"{plan.step:g}",
        },
        parameters={
            **dataset.parameters,
            "TIME_TO_DEPTH_SOURCE": dataset.dataset_id,
            "TIME_TO_DEPTH_DEPTH_INDEX": depth_index.index_id,
            "TIME_TO_DEPTH_TIME_INDEX": time_index.index_id if time_index else "",
            "TIME_TO_DEPTH_METHOD": plan.method.value,
            "TIME_TO_DEPTH_STEP": f"{plan.step:g}",
            "TIME_TO_DEPTH_INTERPOLATION": (
                "explicit-linear" if plan.method is DepthAggregationMethod.LINEAR else "none"
            ),
        },
        indexes=indexes,
        active_index_id=depth_id,
        version_headers=dict(dataset.version_headers),
    )

    for curve in dataset.curves.values():
        values = np.asarray(curve.values, dtype=np.float64)
        if plan.method is DepthAggregationMethod.LINEAR:
            converted = _linear_interpolate(source_depth, values, target_depth)
        else:
            converted = np.asarray(
                [
                    _aggregate_group(values, rows, source_depth, target, plan.method)
                    for rows, target in zip(groups, target_depth, strict=True)
                ],
                dtype=np.float64,
            )
        curve_id = new_id()
        result.curves[curve_id] = CurveData(
            CurveMetadata(
                curve_id,
                curve.metadata.original_mnemonic,
                curve.metadata.canonical_mnemonic,
                curve.metadata.unit,
                curve.metadata.description,
                dataset_id,
                f"transform:time-to-depth:{dataset.dataset_id}:{plan.method.value}",
            ),
            converted,
        )

    counts = tuple(int(rows.size) for rows in groups)
    return TimeToDepthResult(result, counts, sum(count == 0 for count in counts))


def _target_axis(start: float, stop: float, step: float) -> np.ndarray:
    count = int(np.floor((stop - start) / step + 1e-12)) + 1
    values = start + np.arange(count, dtype=np.float64) * step
    if values[-1] < stop and stop - values[-1] <= step * 1e-9:
        values[-1] = stop
    return values


def _depth_groups(
    source_depth: np.ndarray,
    target_depth: np.ndarray,
    step: float,
) -> tuple[np.ndarray, ...]:
    finite_rows = np.flatnonzero(np.isfinite(source_depth))
    if not finite_rows.size:
        return tuple(np.asarray([], dtype=np.int64) for _ in target_depth)
    positions = np.rint((source_depth[finite_rows] - target_depth[0]) / step).astype(np.int64)
    groups: list[np.ndarray] = []
    for index in range(target_depth.size):
        groups.append(finite_rows[positions == index])
    return tuple(groups)


def _aggregate_group(
    values: np.ndarray,
    rows: np.ndarray,
    source_depth: np.ndarray,
    target_depth: float,
    method: DepthAggregationMethod,
) -> float:
    if not rows.size:
        return np.nan
    finite_rows = rows[np.isfinite(values[rows])]
    if not finite_rows.size:
        return np.nan
    selected = values[finite_rows]
    if method is DepthAggregationMethod.FIRST:
        return float(selected[0])
    if method is DepthAggregationMethod.LAST:
        return float(selected[-1])
    if method is DepthAggregationMethod.MEDIAN:
        return float(np.median(selected))
    if method is DepthAggregationMethod.MIN:
        return float(np.min(selected))
    if method is DepthAggregationMethod.MAX:
        return float(np.max(selected))
    if method is DepthAggregationMethod.NEAREST:
        nearest = finite_rows[int(np.argmin(np.abs(source_depth[finite_rows] - target_depth)))]
        return float(values[nearest])
    return float(np.mean(selected))


def _linear_interpolate(
    source_depth: np.ndarray,
    values: np.ndarray,
    target_depth: np.ndarray,
) -> np.ndarray:
    valid = np.isfinite(source_depth) & np.isfinite(values)
    if np.count_nonzero(valid) < 2:
        return np.full(target_depth.shape, np.nan)
    depths = source_depth[valid]
    source_values = values[valid]
    order = np.argsort(depths, kind="stable")
    depths = depths[order]
    source_values = source_values[order]
    unique, inverse = np.unique(depths, return_inverse=True)
    if unique.size != depths.size:
        sums = np.zeros(unique.shape, dtype=np.float64)
        counts = np.zeros(unique.shape, dtype=np.int64)
        np.add.at(sums, inverse, source_values)
        np.add.at(counts, inverse, 1)
        depths = unique
        source_values = sums / counts
    result = np.interp(target_depth, depths, source_values)
    result[(target_depth < depths[0]) | (target_depth > depths[-1])] = np.nan
    return result


def _aggregate_time_index(
    index: DatasetIndex,
    groups: tuple[np.ndarray, ...],
    source_depth: np.ndarray,
    target_depth: np.ndarray,
) -> np.ndarray:
    raw = np.asarray(index.values)
    if index.index_type is IndexType.DATETIME:
        nanos = raw.astype("datetime64[ns]").astype(np.int64)
        nat = np.iinfo(np.int64).min
        result = np.full(len(groups), nat, dtype=np.int64)
        for position, rows in enumerate(groups):
            valid = rows[nanos[rows] != nat]
            if valid.size:
                base = int(nanos[valid[0]])
                result[position] = base + int(np.mean(nanos[valid] - base))
        return result.astype("datetime64[ns]")
    numeric = np.asarray(raw, dtype=np.float64)
    result = np.full(len(groups), np.nan)
    for position, (rows, target) in enumerate(zip(groups, target_depth, strict=True)):
        valid = rows[np.isfinite(numeric[rows])]
        if valid.size:
            nearest = valid[int(np.argmin(np.abs(source_depth[valid] - target)))]
            result[position] = numeric[nearest]
    return result
