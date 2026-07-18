from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    IndexRole,
    IndexType,
    TimeDepthAggregationPolicy,
    TimeDepthMappingProfile,
    new_id,
)


MAX_TIME_DEPTH_BINS = 5_000_000
_TIME_UNIT_SECONDS = {
    "s": 1.0, "sec": 1.0, "second": 1.0, "ms": 1e-3,
    "us": 1e-6, "ns": 1e-9, "min": 60.0, "h": 3600.0, "hr": 3600.0,
}


@dataclass(frozen=True, slots=True)
class TimeDepthAggregationPlan:
    source_dataset_id: str
    profile_id: str
    interval_seconds: float
    aggregation_policy: TimeDepthAggregationPolicy
    profile_version: int
    source_row_count: int
    valid_row_count: int
    dropped_row_count: int
    target_bin_count: int
    source_fingerprint: str


@dataclass(frozen=True, slots=True)
class TimeDepthAggregationResult:
    dataset: Dataset
    plan: TimeDepthAggregationPlan
    rows_per_bin: tuple[int, ...]


def analyze_time_depth_aggregation(
    dataset: Dataset,
    profile: TimeDepthMappingProfile,
    interval_seconds: float,
) -> TimeDepthAggregationPlan:
    if profile.dataset_id != dataset.dataset_id:
        raise ValueError("TIME↔DEPTH профиль относится к другому набору данных")
    if not isfinite(interval_seconds) or interval_seconds <= 0:
        raise ValueError("Временной интервал должен быть положительным конечным числом")
    time_index = _require_index(dataset, profile.time_index_id, IndexRole.TIME)
    depth_index = _require_index(dataset, profile.depth_index_id, IndexRole.DEPTH)
    seconds, time_valid = _time_seconds(time_index)
    depths = np.asarray(depth_index.values, dtype=np.float64)
    valid = time_valid & np.isfinite(depths)
    valid_count = int(np.count_nonzero(valid))
    if not valid_count:
        raise ValueError("TIME↔DEPTH aggregation не содержит валидных пар")
    bins = _bin_numbers(seconds[valid], interval_seconds)
    target_count = int(np.unique(bins).size)
    if target_count > MAX_TIME_DEPTH_BINS:
        raise ValueError(f"Результат превышает безопасный предел {MAX_TIME_DEPTH_BINS} интервалов")
    if profile.aggregation_policy is TimeDepthAggregationPolicy.ERROR:
        for bin_number in np.unique(bins):
            values = depths[valid][bins == bin_number]
            if np.unique(values).size > 1:
                raise ValueError("Интервал неоднозначно соответствует глубине; выберите политику")
    return TimeDepthAggregationPlan(
        dataset.dataset_id,
        profile.profile_id,
        float(interval_seconds),
        profile.aggregation_policy,
        profile.version,
        int(depths.size),
        valid_count,
        int(depths.size - valid_count),
        target_count,
        _fingerprint(dataset, time_index, depth_index),
    )


def create_time_depth_aggregated_copy(
    dataset: Dataset,
    profile: TimeDepthMappingProfile,
    plan: TimeDepthAggregationPlan,
) -> TimeDepthAggregationResult:
    current = analyze_time_depth_aggregation(dataset, profile, plan.interval_seconds)
    if current != plan:
        raise ValueError("Dataset или TIME↔DEPTH профиль изменился после анализа")
    time_index = _require_index(dataset, profile.time_index_id, IndexRole.TIME)
    depth_index = _require_index(dataset, profile.depth_index_id, IndexRole.DEPTH)
    seconds, time_valid = _time_seconds(time_index)
    depths = np.asarray(depth_index.values, dtype=np.float64)
    valid = time_valid & np.isfinite(depths)
    source_rows = np.flatnonzero(valid)
    bins = _bin_numbers(seconds[valid], plan.interval_seconds)
    unique_bins = np.unique(bins)
    groups = tuple(source_rows[bins == bin_number] for bin_number in unique_bins)
    result_depth = np.asarray(
        [_aggregate_depth(depths[rows], profile.aggregation_policy) for rows in groups],
        dtype=np.float64,
    )
    result_time = _aggregate_times(time_index, groups)
    dataset_id = new_id()
    depth_id = f"{dataset_id}:index:depth"
    time_id = f"{dataset_id}:index:time"
    result = Dataset(
        dataset_id,
        f"{dataset.name} — TIME↔DEPTH {plan.interval_seconds:g} s",
        DatasetKind.DERIVED,
        dataset.depth_domain,
        result_depth,
        source_path=dataset.source_path,
        headers=dict(dataset.headers),
        parameters={
            **dataset.parameters,
            "TIME_DEPTH_SOURCE": dataset.dataset_id,
            "TIME_DEPTH_PROFILE": profile.profile_id,
            "TIME_DEPTH_INTERVAL_SECONDS": f"{plan.interval_seconds:g}",
            "TIME_DEPTH_POLICY": profile.aggregation_policy.value,
        },
        indexes={
            depth_id: DatasetIndex(
                depth_id, depth_index.mnemonic, depth_index.index_type, IndexRole.DEPTH,
                depth_index.unit, result_depth,
                evidence=depth_index.evidence + (f"time-depth:{profile.profile_id}",),
            ),
            time_id: DatasetIndex(
                time_id, time_index.mnemonic, time_index.index_type, IndexRole.TIME,
                time_index.unit, result_time, timezone=time_index.timezone,
                datetime_format=time_index.datetime_format,
                evidence=time_index.evidence + (f"time-depth:{profile.profile_id}",),
            ),
        },
        active_index_id=depth_id,
    )
    for curve in dataset.curves.values():
        values = np.asarray(curve.values, dtype=np.float64)
        aggregated = np.asarray([_finite_mean(values[rows]) for rows in groups])
        curve_id = new_id()
        result.curves[curve_id] = CurveData(
            CurveMetadata(
                curve_id,
                curve.metadata.original_mnemonic,
                curve.metadata.canonical_mnemonic,
                curve.metadata.unit,
                curve.metadata.description,
                dataset_id,
                f"transform:time-depth:{dataset.dataset_id}:{profile.profile_id}:v{profile.version}",
            ),
            aggregated,
        )
    return TimeDepthAggregationResult(result, plan, tuple(len(rows) for rows in groups))


def _require_index(dataset: Dataset, index_id: str, role: IndexRole) -> DatasetIndex:
    index = dataset.indexes.get(index_id)
    if index is None or index.role is not role:
        raise ValueError(f"Индекс {index_id} не имеет роль {role.value}")
    return index


def _time_seconds(index: DatasetIndex) -> tuple[np.ndarray, np.ndarray]:
    raw = np.asarray(index.values)
    if index.index_type is IndexType.DATETIME:
        valid = ~np.isnat(raw)
        result = np.full(raw.shape, np.nan)
        if np.any(valid):
            nanos = raw[valid].astype("datetime64[ns]").astype(np.int64)
            origin = int(np.min(nanos))
            result[valid] = (nanos - origin).astype(np.float64) / 1e9
        return result, valid
    unit = (index.unit or "").strip().casefold()
    factor = _TIME_UNIT_SECONDS.get(unit)
    if factor is None:
        raise ValueError(f"Единица относительного времени не поддерживается: {index.unit or '—'}")
    result = np.asarray(raw, dtype=np.float64) * factor
    return result, np.isfinite(result)


def _bin_numbers(seconds: np.ndarray, interval: float) -> np.ndarray:
    origin = float(np.min(seconds))
    return np.floor((seconds - origin) / interval + 1e-12).astype(np.int64)


def _aggregate_depth(values: np.ndarray, policy: TimeDepthAggregationPolicy) -> float:
    if policy in {TimeDepthAggregationPolicy.ERROR, TimeDepthAggregationPolicy.FIRST}:
        return float(values[0])
    if policy is TimeDepthAggregationPolicy.LAST:
        return float(values[-1])
    if policy is TimeDepthAggregationPolicy.MIN:
        return float(np.min(values))
    if policy is TimeDepthAggregationPolicy.MAX:
        return float(np.max(values))
    return float(np.mean(values))


def _aggregate_times(index: DatasetIndex, groups: tuple[np.ndarray, ...]) -> np.ndarray:
    raw = np.asarray(index.values)
    if index.index_type is IndexType.DATETIME:
        nanos = raw.astype("datetime64[ns]").astype(np.int64)
        means = np.asarray(
            [
                int(nanos[rows][0])
                + int(np.mean(nanos[rows] - int(nanos[rows][0])))
                for rows in groups
            ],
            dtype=np.int64,
        )
        return means.astype("datetime64[ns]")
    numeric = np.asarray(raw, dtype=np.float64)
    return np.asarray([np.mean(numeric[rows]) for rows in groups], dtype=np.float64)


def _finite_mean(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    return float(np.mean(finite)) if finite.size else np.nan


def _fingerprint(
    dataset: Dataset, time_index: DatasetIndex, depth_index: DatasetIndex
) -> str:
    digest = sha256()
    digest.update(np.asarray(time_index.values).tobytes())
    digest.update(np.asarray(depth_index.values, dtype=np.float64).tobytes())
    for curve_id, curve in sorted(dataset.curves.items()):
        digest.update(curve_id.encode("utf-8"))
        digest.update(str(curve.version).encode("ascii"))
        digest.update(np.asarray(curve.values, dtype=np.float64).tobytes())
    return digest.hexdigest()
