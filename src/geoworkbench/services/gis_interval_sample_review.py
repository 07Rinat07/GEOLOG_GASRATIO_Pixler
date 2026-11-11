"""Count actual samples in a reviewed GIS source within an MD window.

This snapshot describes points, not continuous coverage or interpretation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite

import numpy as np

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_input_inventory import GisCurveInput, inventory_gis_inputs
from geoworkbench.services.gis_reference_input_review import (
    GisReferenceInputReview, review_gis_reference_input,
)


@dataclass(frozen=True, slots=True)
class GisIntervalSampleReview:
    source: GisReferenceInputReview
    top_md_m: float
    bottom_md_m: float
    sample_count: int
    finite_count: int
    missing_count: int
    finite_md_bounds: tuple[float, float] | None
    missing_md_preview: tuple[float, ...] = ()
    finite_value_bounds: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class GisSourceIntervalSampleReview:
    """Observed values only; does not authorize a petrophysical calculation."""

    source: GisCurveInput
    top_md_m: float
    bottom_md_m: float
    sample_count: int
    finite_count: int
    missing_count: int
    finite_md_bounds: tuple[float, float] | None
    missing_md_preview: tuple[float, ...] = ()
    finite_value_bounds: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class GisSourceIntervalBatchItem:
    """One requested curve, either reviewed or explicitly blocked."""

    curve_key: str
    source: GisCurveInput | None
    issues: tuple[str, ...]
    review: GisSourceIntervalSampleReview | None


MAX_GIS_INTERVAL_CURVES = 8


class GisIntervalReviewCancelled(Exception):
    """A read-only interval review was cancelled between processing stages."""


@dataclass(frozen=True, slots=True)
class _IntervalSummary:
    sample_count: int
    finite_count: int
    missing_count: int
    finite_md_bounds: tuple[float, float] | None
    missing_md_preview: tuple[float, ...]
    finite_value_bounds: tuple[float, float] | None


def review_gis_interval_samples(
    dataset: Dataset, *, method_id: str, curve_key: str,
    top_md_m: float, bottom_md_m: float,
) -> GisIntervalSampleReview:
    """Review source and count actual rows in the closed metre-MD window.

    Missing/non-finite values count as missing; zero is a measured value.
    Bounds do not imply coverage between observations. No values are filled,
    interpreted, calibrated or aligned with another dataset.
    """
    top, bottom = _interval_bounds(top_md_m, bottom_md_m)
    source = review_gis_reference_input(dataset, method_id=method_id, curve_key=curve_key)
    if not source.ready_for_calibration:
        raise ValueError("GIS source review failed: " + ", ".join(source.issues))
    summary = _summarize_samples(dataset, curve_key, top, bottom)
    return GisIntervalSampleReview(
        source, top, bottom, summary.sample_count, summary.finite_count, summary.missing_count,
        summary.finite_md_bounds, summary.missing_md_preview, summary.finite_value_bounds,
    )


def review_gis_source_interval_samples(
    dataset: Dataset, *, curve_key: str, top_md_m: float, bottom_md_m: float,
) -> GisSourceIntervalSampleReview:
    """Review explicit verified source rows without selecting a calculation method.

    These are raw observations, not calibration, continuous coverage or evidence
    of geological alignment. Unsupported units, axes and provenance are rejected.
    """
    top, bottom = _interval_bounds(top_md_m, bottom_md_m)
    if not isinstance(curve_key, str) or not curve_key.strip():
        raise ValueError("An explicit curve key is required")
    inventory = inventory_gis_inputs(dataset)
    source = next((row for row in inventory.curves if row.curve_key == curve_key), None)
    # A correctly shaped curve containing only missing samples is still useful
    # for an availability review; it must never be treated as calibration input.
    if source is None or inventory.axis_issues or any(
        issue != "no_finite_paired_samples" for issue in source.issues
    ):
        raise ValueError("GIS source review failed")
    summary = _summarize_samples(dataset, curve_key, top, bottom)
    return GisSourceIntervalSampleReview(
        source, top, bottom, summary.sample_count, summary.finite_count, summary.missing_count,
        summary.finite_md_bounds, summary.missing_md_preview, summary.finite_value_bounds,
    )


def review_gis_source_interval_batch(
    dataset: Dataset, *, curve_keys: tuple[str, ...], top_md_m: float, bottom_md_m: float,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> tuple[GisSourceIntervalBatchItem, ...]:
    """Review explicitly selected sources on one axis without interpolation or inference.

    Invalid sources remain visible as blocked rows. Inventory is rebuilt once for
    the operation; no measurement is substituted and no calibration is created.
    """
    top, bottom = _interval_bounds(top_md_m, bottom_md_m)
    if (
        not isinstance(curve_keys, tuple) or not 1 <= len(curve_keys) <= MAX_GIS_INTERVAL_CURVES
        or any(not isinstance(key, str) or not key.strip() for key in curve_keys)
        or len(set(curve_keys)) != len(curve_keys)
    ):
        raise ValueError("Select one to eight unique GIS curve keys")
    if cancelled is not None and cancelled():
        raise GisIntervalReviewCancelled
    inventory = inventory_gis_inputs(dataset)
    sources = {source.curve_key: source for source in inventory.curves}
    result: list[GisSourceIntervalBatchItem] = []
    for index, key in enumerate(curve_keys):
        if cancelled is not None and cancelled():
            raise GisIntervalReviewCancelled
        source = sources.get(key)
        issues = tuple(f"axis:{issue}" for issue in inventory.axis_issues)
        if source is None:
            issues += ("curve_not_found",)
        else:
            issues += tuple(
                f"curve:{issue}" for issue in source.issues if issue != "no_finite_paired_samples"
            )
        if issues or source is None:
            result.append(GisSourceIntervalBatchItem(key, source, issues, None))
        else:
            summary = _summarize_samples(dataset, key, top, bottom, cancelled=cancelled)
            review = GisSourceIntervalSampleReview(
                source, top, bottom, summary.sample_count, summary.finite_count, summary.missing_count,
                summary.finite_md_bounds, summary.missing_md_preview, summary.finite_value_bounds,
            )
            result.append(GisSourceIntervalBatchItem(key, source, (), review))
        if progress is not None:
            progress(index + 1, len(curve_keys))
    if cancelled is not None and cancelled():
        raise GisIntervalReviewCancelled
    return tuple(result)


def _interval_bounds(top_md_m: float, bottom_md_m: float) -> tuple[float, float]:
    bounds: list[float] = []
    for value in (top_md_m, bottom_md_m):
        scalar = np.asarray(value)
        if scalar.ndim != 0 or scalar.dtype.kind not in "fiu" or not np.isfinite(scalar).all():
            raise ValueError("Interval bounds must be finite numeric MD values")
        bounds.append(float(scalar))
    top, bottom = bounds
    if not (isfinite(top) and isfinite(bottom) and top < bottom and isfinite(bottom - top)):
        raise ValueError("Interval bounds must be ordered finite MD values")
    return top, bottom


def _summarize_samples(
    dataset: Dataset, curve_key: str, top: float, bottom: float,
    cancelled: Callable[[], bool] | None = None,
) -> _IntervalSummary:
    """Scan actual MD rows in bounded chunks; never invent missing samples.

    A batch review checks cancellation inside one large curve, not just between
    curves. Keep preview depths in original LAS order (including descending MD).
    """
    depths = np.asarray(dataset.active_index.values)
    values = np.asarray(dataset.curves[curve_key].values)
    total = 0
    finite = 0
    preview: list[float] = []
    depth_min, depth_max = float("inf"), float("-inf")
    value_min, value_max = float("inf"), float("-inf")
    for start in range(0, len(depths), 65_536):
        if cancelled is not None and cancelled():
            raise GisIntervalReviewCancelled
        stop = min(start + 65_536, len(depths))
        chunk_depths = depths[start:stop]
        chunk_values = values[start:stop]
        selected = (chunk_depths >= top) & (chunk_depths <= bottom)
        count = int(np.count_nonzero(selected))
        if not count:
            continue
        finite_values = np.isfinite(chunk_values)
        observed = selected & finite_values
        present = int(np.count_nonzero(observed))
        total += count
        finite += present
        if present:
            measured_depths = chunk_depths[observed]
            measured_values = chunk_values[observed]
            depth_min = min(depth_min, float(np.min(measured_depths)))
            depth_max = max(depth_max, float(np.max(measured_depths)))
            value_min = min(value_min, float(np.min(measured_values)))
            value_max = max(value_max, float(np.max(measured_values)))
        if count != present and len(preview) < 10:
            missing = np.flatnonzero(selected & ~finite_values)
            preview.extend(
                float(chunk_depths[index]) for index in missing[:10 - len(preview)]
            )
    if cancelled is not None and cancelled():
        raise GisIntervalReviewCancelled
    return _IntervalSummary(
        total, finite, total - finite,
        (depth_min, depth_max) if finite else None,
        tuple(preview),
        (value_min, value_max) if finite else None,
    )
