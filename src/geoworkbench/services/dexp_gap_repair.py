from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


Array = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
LabelArray = NDArray[np.integer]


@dataclass(frozen=True, slots=True)
class DexpGapRepairResult:
    """Result of conservative, depth-aware interpolation of internal DEXP gaps."""

    values: Array
    repaired_mask: BoolArray
    repaired_points: int
    repaired_gaps: int
    remaining_missing_points: int


_DEFAULT_MAX_GAP_SAMPLES = 64
_METRE_GAP_LIMIT = 6.0
_FEET_GAP_LIMIT = 20.0


def repair_dexp_short_gaps(
    depth: Array,
    values: Array,
    *,
    depth_unit: str = "",
    max_gap_samples: int = _DEFAULT_MAX_GAP_SAMPLES,
    max_gap_span: float | None = None,
    segment_labels: LabelArray | None = None,
    repairable_mask: BoolArray | None = None,
) -> DexpGapRepairResult:
    """Interpolate only short internal gaps bounded by valid DEXP samples.

    The source arrays are never modified in place. Leading, trailing and long
    gaps remain missing so that the application does not invent a curve across
    an interval with insufficient drilling data. When drilling-mode labels are
    supplied, both anchors and every missing sample must belong to the same
    mode. ``repairable_mask`` additionally prevents interpolation through slide
    intervals where downhole/bit RPM is unavailable.
    """

    axis = np.asarray(depth, dtype=np.float64)
    source = np.asarray(values, dtype=np.float64)
    if axis.ndim != 1 or source.ndim != 1:
        raise ValueError("Глубина и DEXP должны быть одномерными массивами")
    if axis.shape != source.shape:
        raise ValueError("Глубина и DEXP должны иметь одинаковую длину")
    if max_gap_samples < 1:
        raise ValueError("Максимальный размер разрыва должен быть не меньше одной точки")

    labels = _optional_labels(segment_labels, source.shape)
    allowed = _optional_mask(repairable_mask, source.shape)
    repaired = source.copy()
    repaired_mask = np.zeros(source.shape, dtype=bool)
    finite_depth = np.isfinite(axis)
    missing = finite_depth & ~np.isfinite(source)
    if not np.any(missing):
        return DexpGapRepairResult(repaired, repaired_mask, 0, 0, 0)

    span_limit = (
        float(max_gap_span)
        if max_gap_span is not None
        else _recommended_gap_span(axis, finite_depth, depth_unit, max_gap_samples)
    )
    if not np.isfinite(span_limit) or span_limit <= 0.0:
        raise ValueError("Максимальная протяжённость разрыва должна быть больше нуля")

    indices = np.flatnonzero(missing)
    split_points = np.flatnonzero(np.diff(indices) > 1) + 1
    groups = np.split(indices, split_points)
    repaired_gaps = 0

    for group in groups:
        if group.size == 0 or group.size > max_gap_samples:
            continue
        left = int(group[0]) - 1
        right = int(group[-1]) + 1
        if left < 0 or right >= source.size:
            continue
        if not (
            finite_depth[left]
            and finite_depth[right]
            and np.isfinite(source[left])
            and np.isfinite(source[right])
        ):
            continue
        if allowed is not None and not np.all(allowed[np.r_[left, group, right]]):
            continue
        if labels is not None:
            section = labels[np.r_[left, group, right]]
            if section.size == 0 or section[0] <= 0 or not np.all(section == section[0]):
                continue
        # DEXP is physically meaningful only for positive anchor values. A gap
        # next to an invalid output remains visible and is explained by QC.
        if source[left] <= 0.0 or source[right] <= 0.0:
            continue

        anchor_span = abs(float(axis[right] - axis[left]))
        if not np.isfinite(anchor_span) or anchor_span <= 0.0 or anchor_span > span_limit:
            continue

        denominator = float(axis[right] - axis[left])
        fractions = (axis[group] - axis[left]) / denominator
        interpolated = source[left] + fractions * (source[right] - source[left])
        valid_interpolation = np.isfinite(interpolated) & (interpolated > 0.0)
        if not np.all(valid_interpolation):
            continue

        repaired[group] = interpolated
        repaired_mask[group] = True
        repaired_gaps += 1

    remaining = finite_depth & ~np.isfinite(repaired)
    return DexpGapRepairResult(
        repaired,
        repaired_mask,
        int(np.count_nonzero(repaired_mask)),
        repaired_gaps,
        int(np.count_nonzero(remaining)),
    )


def _optional_labels(
    value: LabelArray | None,
    shape: tuple[int, ...],
) -> NDArray[np.int64] | None:
    if value is None:
        return None
    result = np.asarray(value, dtype=np.int64)
    if result.ndim != 1 or result.shape != shape:
        raise ValueError("Метки режима должны совпадать по форме с DEXP")
    return result


def _optional_mask(
    value: BoolArray | None,
    shape: tuple[int, ...],
) -> BoolArray | None:
    if value is None:
        return None
    result = np.asarray(value, dtype=bool)
    if result.ndim != 1 or result.shape != shape:
        raise ValueError("Маска восстановления должна совпадать по форме с DEXP")
    return result


def _recommended_gap_span(
    depth: Array,
    finite_depth: BoolArray,
    depth_unit: str,
    max_gap_samples: int,
) -> float:
    normalized_unit = depth_unit.strip().casefold().replace(".", "")
    if normalized_unit in {"m", "meter", "metre", "meters", "metres", "м"}:
        return _METRE_GAP_LIMIT
    if normalized_unit in {"ft", "feet", "foot", "фут", "футы"}:
        return _FEET_GAP_LIMIT

    finite_axis = depth[finite_depth]
    if finite_axis.size < 2:
        return float(max_gap_samples)
    steps = np.abs(np.diff(finite_axis))
    steps = steps[np.isfinite(steps) & (steps > 0.0)]
    if not steps.size:
        return float(max_gap_samples)
    return float(np.median(steps)) * float(max_gap_samples + 1)


__all__ = ["DexpGapRepairResult", "repair_dexp_short_gaps"]
