"""Count actual samples in a reviewed GIS source within an MD window.

This snapshot describes points, not continuous coverage or interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from geoworkbench.domain.models import Dataset
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


def review_gis_interval_samples(
    dataset: Dataset, *, method_id: str, curve_key: str,
    top_md_m: float, bottom_md_m: float,
) -> GisIntervalSampleReview:
    """Review source and count actual rows in the closed metre-MD window.

    Missing/non-finite values count as missing; zero is a measured value.
    Bounds do not imply coverage between observations. No values are filled,
    interpreted, calibrated or aligned with another dataset.
    """
    bounds: list[float] = []
    for value in (top_md_m, bottom_md_m):
        scalar = np.asarray(value)
        if scalar.ndim != 0 or scalar.dtype.kind not in "fiu" or not np.isfinite(scalar).all():
            raise ValueError("Interval bounds must be finite numeric MD values")
        bounds.append(float(scalar))
    top, bottom = bounds
    if not (isfinite(top) and isfinite(bottom) and top < bottom and isfinite(bottom - top)):
        raise ValueError("Interval bounds must be ordered finite MD values")
    source = review_gis_reference_input(dataset, method_id=method_id, curve_key=curve_key)
    if not source.ready_for_calibration:
        raise ValueError("GIS source review failed: " + ", ".join(source.issues))
    depths = np.asarray(dataset.active_index.values)
    values = np.asarray(dataset.curves[curve_key].values)
    selected = (depths >= top) & (depths <= bottom)
    observed = selected & np.isfinite(values)
    total, finite = int(np.count_nonzero(selected)), int(np.count_nonzero(observed))
    finite_depths = depths[observed]
    # Bound temporary index arrays even if a large LAS has many missing rows.
    preview: list[float] = []
    if finite != total:
        for start in range(0, len(depths), 65_536):
            stop = min(start + 65_536, len(depths))
            missing_indices = np.flatnonzero(selected[start:stop] & ~np.isfinite(values[start:stop]))
            preview.extend(float(depths[start + index]) for index in missing_indices[:10 - len(preview)])
            if len(preview) == 10:
                break
    observed_bounds = (
        (float(np.min(finite_depths)), float(np.max(finite_depths))) if finite else None
    )
    return GisIntervalSampleReview(
        source, top, bottom, total, finite, total - finite, observed_bounds, tuple(preview),
    )
