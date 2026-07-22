from __future__ import annotations

from datetime import datetime, timedelta
import math
from pathlib import Path

import numpy as np

from .models import (
    DatasetClassification,
    IndexCandidate,
    IssueSeverity,
    ParadoxFieldType,
    ParadoxIssue,
    ParadoxTable,
    QualitySummary,
)


_OLE_EPOCH = datetime(1899, 12, 30)
_DEPTH_NAME_HINTS = {"DEPT", "DEPTH", "MD", "TVD", "TVDSS", "HOLEDEPTH", "BITDEPTH"}
_TIME_NAME_HINTS = {"TIME", "DATETIME", "TIMESTAMP", "ETIME", "EPOCH", "UNIXTIME", "LOGTIME", "S0"}


def analyze_table(table: ParadoxTable) -> QualitySummary:
    depth: list[IndexCandidate] = []
    time: list[IndexCandidate] = []
    issues = [*table.issues, *_table_quality_issues(table)]
    for field in table.fields:
        column = table.columns[field.name]
        if not field.is_numeric or column.is_empty:
            if column.is_empty:
                issues.append(
                    ParadoxIssue(
                        IssueSeverity.INFO,
                        "empty-channel",
                        f"Канал {field.name} полностью пуст",
                        table.source,
                        field_name=field.name,
                        field_type=field.type_name,
                        details={"field": field.name},
                    )
                )
            continue
        values = np.asarray(column.values, dtype=np.float64)
        depth_candidate = _depth_candidate(field.name, values)
        if depth_candidate.confidence >= 0.25:
            depth.append(depth_candidate)
        time_candidate = _time_candidate(field.name, values)
        if time_candidate.confidence >= 0.25:
            time.append(time_candidate)

    depth.sort(key=lambda item: item.confidence, reverse=True)
    time.sort(key=lambda item: item.confidence, reverse=True)
    classification = _classify(depth, time)
    issues.extend(_quality_issues(table, depth[0] if depth else None, time[0] if time else None))
    return QualitySummary(classification, tuple(depth), tuple(time), tuple(issues))


def convert_time_values(values: np.ndarray) -> tuple[np.ndarray, np.ndarray | None, str]:
    """Return elapsed seconds, optional datetime64 and detected representation."""

    numeric = np.asarray(values, dtype=np.float64)
    finite = numeric[np.isfinite(numeric)]
    if not finite.size:
        return np.full(numeric.shape, np.nan), None, "unknown"
    median = float(np.median(finite))
    if 10_000 <= median <= 100_000:
        datetimes = np.full(numeric.shape, np.datetime64("NaT", "ns"))
        for index, value in enumerate(numeric):
            if not math.isfinite(float(value)):
                continue
            moment = _OLE_EPOCH + timedelta(days=float(value))
            datetimes[index] = np.datetime64(moment, "ns")
        elapsed = _elapsed_from_datetime(datetimes)
        return elapsed, datetimes, "ole-automation-days"
    scale = _unix_scale(median)
    if scale is not None:
        factor, unit = scale
        seconds = numeric / factor
        datetimes = np.full(numeric.shape, np.datetime64("NaT", "ns"))
        finite_mask = np.isfinite(seconds)
        nanoseconds = np.rint(seconds[finite_mask] * 1_000_000_000).astype(np.int64)
        datetimes[finite_mask] = nanoseconds.astype("datetime64[ns]")
        return _elapsed_from_datetime(datetimes), datetimes, f"unix-{unit}"
    first = float(finite[0])
    elapsed = numeric - first
    # Large stable increments are often milliseconds; normalize conservatively.
    positive = np.diff(finite)
    positive = positive[positive > 0]
    median_step = float(np.median(positive)) if positive.size else 0.0
    if median_step > 100:
        elapsed = elapsed / 1000.0
        return elapsed, None, "relative-milliseconds"
    return elapsed, None, "relative-seconds"


def _table_quality_issues(table: ParadoxTable) -> list[ParadoxIssue]:
    issues: list[ParadoxIssue] = []
    row_has_value = np.zeros(table.rows_read, dtype=bool)
    known_types = {int(item) for item in ParadoxFieldType}
    for field in table.fields:
        column = table.columns[field.name]
        if field.type_code not in known_types:
            issues.append(
                ParadoxIssue(
                    IssueSeverity.WARNING,
                    "unknown-field-type",
                    (
                        f"Поле {field.name} имеет неизвестный тип {field.type_code}; "
                        "исходные байты сохранены"
                    ),
                    table.source,
                    field_name=field.name,
                    field_type=field.type_name,
                    details={"field": field.name, "type": field.type_code},
                )
            )
        if field.is_numeric:
            values = np.asarray(column.values, dtype=np.float64)
            finite_mask = np.isfinite(values)
            row_has_value |= finite_mask
            infinity_count = int(np.count_nonzero(np.isinf(values)))
            if infinity_count:
                issues.append(
                    ParadoxIssue(
                        IssueSeverity.ERROR,
                        "infinite-values",
                        f"Канал {field.name} содержит Infinity: {infinity_count}",
                        table.source,
                        field_name=field.name,
                        field_type=field.type_name,
                        details={"field": field.name, "count": infinity_count},
                    )
                )
            huge_count = int(np.count_nonzero(finite_mask & (np.abs(values) > 1e100)))
            if huge_count:
                issues.append(
                    ParadoxIssue(
                        IssueSeverity.WARNING,
                        "huge-values",
                        f"Канал {field.name} содержит чрезмерно большие значения: {huge_count}",
                        table.source,
                        field_name=field.name,
                        field_type=field.type_name,
                        details={"field": field.name, "count": huge_count},
                    )
                )
            finite = values[finite_mask]
            if finite.size >= 20:
                median = float(np.median(finite))
                mad = float(np.median(np.abs(finite - median)))
                if mad > 0:
                    robust_z = np.abs(finite - median) / (1.4826 * mad)
                    outlier_count = int(np.count_nonzero(robust_z > 12.0))
                    if outlier_count:
                        issues.append(
                            ParadoxIssue(
                                IssueSeverity.INFO,
                                "statistical-outliers",
                                (
                                    f"Канал {field.name}: статистических выбросов "
                                    f"для проверки {outlier_count}"
                                ),
                                table.source,
                                field_name=field.name,
                                field_type=field.type_name,
                                details={"field": field.name, "count": outlier_count},
                            )
                        )
        else:
            values = np.asarray(column.values, dtype=object)
            row_has_value |= np.fromiter(
                (item not in (None, "", b"") for item in values),
                dtype=bool,
                count=values.size,
            )
    empty_rows = int(np.count_nonzero(~row_has_value))
    if empty_rows:
        issues.append(
            ParadoxIssue(
                IssueSeverity.WARNING,
                "empty-rows",
                f"Обнаружено полностью пустых строк: {empty_rows}",
                table.source,
                details={"count": empty_rows},
            )
        )
    return issues


def _depth_candidate(name: str, values: np.ndarray) -> IndexCandidate:
    finite = values[np.isfinite(values)]
    evidence: list[str] = []
    warnings: list[str] = []
    if finite.size < 2:
        return IndexCandidate(name, "depth", 0.0, (), ("недостаточно значений",))
    score = min(0.20, 0.20 * finite.size / max(1, values.size))
    normalized = name.upper().replace(" ", "")
    if normalized in _DEPTH_NAME_HINTS:
        score += 0.30
        evidence.append("название соответствует глубинному индексу")
    differences = np.diff(finite)
    nonnegative_ratio = float(np.mean(differences >= 0)) if differences.size else 0.0
    positive = differences[differences > 0]
    if nonnegative_ratio >= 0.995:
        score += 0.28
        evidence.append("значения практически монотонно возрастают")
    elif nonnegative_ratio >= 0.95:
        score += 0.20
        evidence.append("большинство значений возрастает")
    else:
        warnings.append("обнаружен обратный ход")
    span = float(np.max(finite) - np.min(finite))
    if 10 <= span <= 20_000 and -2_000 <= float(np.min(finite)) <= 20_000:
        score += 0.15
        evidence.append("диапазон правдоподобен для глубины")
    elif span <= 0:
        warnings.append("нулевой диапазон")
    if positive.size:
        median_step = float(np.median(positive))
        deviations = np.abs(positive - median_step)
        stable_ratio = float(np.mean(deviations <= max(1e-9, abs(median_step) * 0.05)))
        if median_step > 0 and stable_ratio >= 0.90:
            score += 0.22
            evidence.append(f"стабильный шаг около {median_step:g}")
        elif median_step > 0 and stable_ratio >= 0.60:
            score += 0.12
            evidence.append(f"преимущественный шаг около {median_step:g}")
        else:
            warnings.append("шаг нестабилен")
    duplicate_count = int(finite.size - np.unique(finite).size)
    if duplicate_count:
        warnings.append(f"повторов: {duplicate_count}")
        score -= min(0.12, duplicate_count / finite.size)
    if _looks_like_ole_date(finite):
        score -= 0.45
        warnings.append("значения похожи на календарное время OLE/Delphi")
    return IndexCandidate(
        name,
        "depth",
        max(0.0, min(score, 1.0)),
        tuple(evidence),
        tuple(warnings),
    )


def _time_candidate(name: str, values: np.ndarray) -> IndexCandidate:
    finite = values[np.isfinite(values)]
    evidence: list[str] = []
    warnings: list[str] = []
    if finite.size < 2:
        return IndexCandidate(name, "time", 0.0, (), ("недостаточно значений",))
    score = min(0.15, 0.15 * finite.size / max(1, values.size))
    normalized = name.upper().replace(" ", "")
    if normalized in _TIME_NAME_HINTS:
        score += 0.30
        evidence.append("название соответствует времени")
    differences = np.diff(finite)
    monotonic_ratio = float(np.mean(differences >= 0)) if differences.size else 0.0
    if monotonic_ratio >= 0.995:
        score += 0.20
        evidence.append("время монотонно")
    elif monotonic_ratio < 0.95:
        warnings.append("нарушена хронология")
    preview = None
    median = float(np.median(finite))
    if _looks_like_ole_date(finite):
        score += 0.48
        evidence.append("диапазон соответствует Delphi/OLE Automation date")
        try:
            moment = _OLE_EPOCH + timedelta(days=float(finite[0]))
            preview = moment.strftime("%d.%m.%Y %H:%M:%S")
        except (OverflowError, ValueError):
            pass
    elif _unix_scale(median) is not None:
        score += 0.42
        factor, unit = _unix_scale(median)  # type: ignore[misc]
        evidence.append(f"диапазон соответствует Unix timestamp ({unit})")
        try:
            preview = datetime.utcfromtimestamp(float(finite[0]) / factor).strftime(
                "%d.%m.%Y %H:%M:%S"
            )
        except (OverflowError, OSError, ValueError):
            pass
    else:
        positive = differences[differences > 0]
        if positive.size and np.median(positive) > 0:
            score += 0.12
            evidence.append("последовательный числовой индекс времени")
    return IndexCandidate(
        name,
        "time",
        max(0.0, min(score, 1.0)),
        tuple(evidence),
        tuple(warnings),
        preview,
    )


def _classify(depth: list[IndexCandidate], time: list[IndexCandidate]) -> DatasetClassification:
    depth_conf = depth[0].confidence if depth else 0.0
    time_conf = time[0].confidence if time else 0.0
    depth_ambiguous = len(depth) > 1 and depth[1].confidence >= max(0.65, depth_conf - 0.05)
    time_ambiguous = len(time) > 1 and time[1].confidence >= max(0.65, time_conf - 0.05)
    if depth_ambiguous or time_ambiguous:
        return DatasetClassification.MIXED
    if depth_conf >= 0.65 and time_conf >= 0.65:
        return DatasetClassification.TIME_WITH_DEPTH
    if depth_conf >= 0.65:
        return DatasetClassification.DEPTH
    if time_conf >= 0.65:
        return DatasetClassification.TIME
    return DatasetClassification.UNDEFINED


def _quality_issues(
    table: ParadoxTable,
    depth: IndexCandidate | None,
    time: IndexCandidate | None,
) -> list[ParadoxIssue]:
    issues: list[ParadoxIssue] = []
    if depth is not None:
        values = np.asarray(table.columns[depth.field_name].values, dtype=np.float64)
        finite = values[np.isfinite(values)]
        if finite.size:
            duplicates = int(finite.size - np.unique(finite).size)
            if duplicates:
                issues.append(
                    ParadoxIssue(
                        IssueSeverity.WARNING,
                        "duplicate-depth",
                        f"В кандидате глубины {depth.field_name} обнаружено повторов: {duplicates}",
                        table.source,
                        field_name=depth.field_name,
                        details={"field": depth.field_name, "count": duplicates},
                    )
                )
            reverse = int(np.sum(np.diff(finite) < 0))
            if reverse:
                issues.append(
                    ParadoxIssue(
                        IssueSeverity.WARNING,
                        "reverse-depth",
                        f"В кандидате глубины {depth.field_name} обратных шагов: {reverse}",
                        table.source,
                        field_name=depth.field_name,
                        details={"field": depth.field_name, "count": reverse},
                    )
                )
            if np.any(finite < 0):
                issues.append(
                    ParadoxIssue(
                        IssueSeverity.WARNING,
                        "negative-depth",
                        f"Кандидат глубины {depth.field_name} содержит отрицательные значения",
                        table.source,
                        field_name=depth.field_name,
                        details={"field": depth.field_name},
                    )
                )
            raw = np.asarray(table.columns[depth.field_name].values, dtype=np.float64)
            valid_pairs = np.isfinite(raw[:-1]) & np.isfinite(raw[1:])
            deltas = np.diff(raw)
            positive = deltas[valid_pairs & (deltas > 0)]
            if positive.size:
                nominal = float(np.median(positive))
                threshold = max(abs(nominal) * 10.0, 1.0)
                jump_rows = np.flatnonzero(valid_pairs & (np.abs(deltas) > threshold))
                for row in jump_rows[:100]:
                    issues.append(
                        ParadoxIssue(
                            IssueSeverity.WARNING,
                            "depth-jump",
                            (
                                f"Резкий скачок глубины: {raw[row]:g} → {raw[row + 1]:g}; "
                                f"номинальный шаг {nominal:g}"
                            ),
                            table.source,
                            record_number=int(row + 2),
                            field_name=depth.field_name,
                            details={
                                "field": depth.field_name,
                                "previous": float(raw[row]),
                                "current": float(raw[row + 1]),
                                "nominal": nominal,
                            },
                        )
                    )
                if jump_rows.size > 100:
                    issues.append(
                        ParadoxIssue(
                            IssueSeverity.INFO,
                            "depth-jump-truncated",
                            f"Дополнительно скрыто скачков глубины: {jump_rows.size - 100}",
                            table.source,
                            field_name=depth.field_name,
                            details={
                                "field": depth.field_name,
                                "count": int(jump_rows.size - 100),
                            },
                        )
                    )
    if time is not None:
        finite = np.asarray(table.columns[time.field_name].values, dtype=np.float64)
        finite = finite[np.isfinite(finite)]
        if finite.size and np.any(np.diff(finite) < 0):
            issues.append(
                ParadoxIssue(
                    IssueSeverity.WARNING,
                    "time-order",
                    f"Канал времени {time.field_name} нарушает хронологию",
                    table.source,
                    field_name=time.field_name,
                    details={"field": time.field_name},
                )
            )
    return issues


def _looks_like_ole_date(values: np.ndarray) -> bool:
    if not values.size:
        return False
    median = float(np.median(values))
    span = float(np.max(values) - np.min(values))
    return 10_000 <= median <= 100_000 and span <= 100_000


def _unix_scale(median: float) -> tuple[float, str] | None:
    absolute = abs(median)
    ranges = (
        (946_684_800, 4_102_444_800, 1.0, "s"),
        (946_684_800_000, 4_102_444_800_000, 1_000.0, "ms"),
        (946_684_800_000_000, 4_102_444_800_000_000, 1_000_000.0, "us"),
        (946_684_800_000_000_000, 4_102_444_800_000_000_000, 1_000_000_000.0, "ns"),
    )
    return next(
        (
            (factor, unit)
            for low, high, factor, unit in ranges
            if low <= absolute <= high
        ),
        None,
    )


def _elapsed_from_datetime(values: np.ndarray) -> np.ndarray:
    result = np.full(values.shape, np.nan, dtype=np.float64)
    valid = ~np.isnat(values)
    if not np.any(valid):
        return result
    nanoseconds = values[valid].astype("datetime64[ns]").astype(np.int64)
    result[valid] = (nanoseconds - nanoseconds[0]) / 1_000_000_000.0
    return result
