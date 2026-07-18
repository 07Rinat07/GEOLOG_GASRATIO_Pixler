from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    IndexRole,
    IndexType,
    TimeDepthAggregationPolicy,
)
from geoworkbench.services.time_normalization import normalize_iso8601_strings


class TimeDepthMappingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TimeDepthMatch:
    time_index_id: str
    depth_index_id: str
    row: int | None
    depth: float
    distance: float
    policy: TimeDepthAggregationPolicy
    matched_rows: tuple[int, ...]


def resolve_time_to_depth(
    dataset: Dataset,
    time_value: str,
    *,
    time_index_id: str | None = None,
    depth_index_id: str | None = None,
    policy: TimeDepthAggregationPolicy = TimeDepthAggregationPolicy.ERROR,
) -> TimeDepthMatch:
    if not isinstance(policy, TimeDepthAggregationPolicy):
        raise TimeDepthMappingError("Неизвестная политика TIME↔DEPTH mapping")
    time_index = _select_index(dataset, IndexRole.TIME, time_index_id)
    depth_index = _select_index(dataset, IndexRole.DEPTH, depth_index_id)
    target, values = _comparable_time(time_index, time_value)
    depths = np.asarray(depth_index.values, dtype=np.float64)
    if values.shape != depths.shape:
        raise TimeDepthMappingError("TIME и DEPTH индексы имеют разную длину")
    valid = np.isfinite(values) & np.isfinite(depths)
    if not np.any(valid):
        raise TimeDepthMappingError("TIME↔DEPTH mapping не содержит валидных пар")
    rows = np.flatnonzero(valid)
    distances = np.abs(values[rows] - target)
    minimum = float(np.min(distances))
    nearest_rows = rows[distances == minimum]
    nearest_depths = np.unique(depths[nearest_rows])
    if policy is TimeDepthAggregationPolicy.ERROR and nearest_depths.size != 1:
        raise TimeDepthMappingError("Временная отметка неоднозначно соответствует глубине")
    row, depth = _aggregate_depth(nearest_rows, depths, policy)
    return TimeDepthMatch(
        time_index.index_id,
        depth_index.index_id,
        row,
        depth,
        minimum,
        policy,
        tuple(int(candidate) for candidate in nearest_rows),
    )


def _aggregate_depth(
    rows: np.ndarray,
    depths: np.ndarray,
    policy: TimeDepthAggregationPolicy,
) -> tuple[int | None, float]:
    if policy in {TimeDepthAggregationPolicy.ERROR, TimeDepthAggregationPolicy.FIRST}:
        row = int(rows[0])
        return row, float(depths[row])
    if policy is TimeDepthAggregationPolicy.LAST:
        row = int(rows[-1])
        return row, float(depths[row])

    candidate_depths = depths[rows]
    if policy is TimeDepthAggregationPolicy.MEAN:
        return None, float(np.mean(candidate_depths))
    target = np.min(candidate_depths) if policy is TimeDepthAggregationPolicy.MIN else np.max(
        candidate_depths
    )
    row = int(rows[np.flatnonzero(candidate_depths == target)[0]])
    return row, float(target)


def _select_index(
    dataset: Dataset, role: IndexRole, requested_id: str | None
) -> DatasetIndex:
    if requested_id is not None:
        index = dataset.indexes.get(requested_id)
        if index is None or index.role is not role:
            raise TimeDepthMappingError(f"Индекс {requested_id} не имеет роль {role.value}")
        return index
    candidates = [index for index in dataset.indexes.values() if index.role is role]
    if len(candidates) != 1:
        raise TimeDepthMappingError(
            f"Для TIME↔DEPTH mapping требуется ровно один индекс роли {role.value}"
        )
    return candidates[0]


def _comparable_time(index: DatasetIndex, raw_value: str) -> tuple[float, np.ndarray]:
    normalized = raw_value.strip()
    if not normalized:
        raise TimeDepthMappingError("Временная отметка не может быть пустой")
    if index.index_type is IndexType.DATETIME:
        parsed = normalize_iso8601_strings(np.asarray([normalized]))
        if parsed is None or np.isnat(parsed.values[0]):
            raise TimeDepthMappingError("Временная отметка должна быть ISO 8601")
        index_is_aware = index.timezone is not None
        value_is_aware = parsed.timezone is not None
        if index_is_aware != value_is_aware:
            raise TimeDepthMappingError(
                "Часовой пояс временной отметки не соответствует TIME индексу"
            )
        target = float(parsed.values[0].astype("datetime64[ns]").astype(np.int64))
        raw = np.asarray(index.values).astype("datetime64[ns]")
        valid = ~np.isnat(raw)
        values = np.full(raw.shape, np.nan, dtype=np.float64)
        values[valid] = raw[valid].astype(np.int64).astype(np.float64)
        return target, values
    try:
        target = float(normalized)
    except ValueError as exc:
        raise TimeDepthMappingError("Относительное время должно быть числом") from exc
    if not np.isfinite(target):
        raise TimeDepthMappingError("Временная отметка должна быть конечной")
    return target, np.asarray(index.values, dtype=np.float64)
