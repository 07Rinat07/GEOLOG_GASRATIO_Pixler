"""Session-local, explicitly reviewed calibration for one actual GIS sample.

Applicability text records the caller's expert evidence; it is not an automatic
certification of a tool or reservoir. No persistence or source mutations occur.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite
from weakref import ReferenceType, ref

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetIndex, IndexRole, IndexType
from geoworkbench.services.gis_reference_input_review import (
    GisReferenceInputReview, review_gis_reference_input,
)
from geoworkbench.services.petrophysical_reference_models import (
    PetrophysicalEstimate, density_porosity, gamma_ray_index,
)


_PARAMETERS = {
    "igr-linear-1": {"clean_reference_api", "shale_reference_api"},
    "density-porosity-1": {"matrix_density_g_cm3", "fluid_density_g_cm3"},
}

# Axis evidence may be edited without changing the source-review summary or MD bytes.
AxisSourceSignature = tuple[
    str, IndexType, IndexRole, str | None, float, tuple[str, ...],
]


@dataclass(frozen=True, slots=True)
class GisReferenceCalibration:
    calibration_id: str
    tool_id: str
    reviewer: str
    applicability_reference: str
    md_bounds: tuple[float, float]
    parameters: tuple[tuple[str, float], ...]
    source: GisReferenceInputReview
    _axis_signature: AxisSourceSignature
    # Weak references detect replacement/reopen without retaining large LAS arrays.
    _depths: ReferenceType[np.ndarray]
    _values: ReferenceType[np.ndarray]
    _depth_sha256: str
    _values_sha256: str


@dataclass(frozen=True, slots=True)
class CalibratedGisSample:
    calibration: GisReferenceCalibration
    sample_index: int
    md_m: float
    source_value: float
    estimate: PetrophysicalEstimate


class GisProfileRowStatus(str, Enum):
    """Distinguish actual calculations from missing or invalid source rows."""

    ESTIMATED = "estimated"
    MISSING_SOURCE = "missing_source"
    INVALID_MEASUREMENT = "invalid_measurement"


@dataclass(frozen=True, slots=True)
class CalibratedGisProfileRow:
    sample_index: int
    md_m: float
    source_value: float | None
    status: GisProfileRowStatus
    estimate: PetrophysicalEstimate | None
    issue: str | None = None


@dataclass(frozen=True, slots=True)
class CalibratedGisProfile:
    """Exact source rows within explicit MD bounds; no continuous coverage claim."""

    calibration: GisReferenceCalibration
    md_bounds: tuple[float, float]
    rows: tuple[CalibratedGisProfileRow, ...]

    @property
    def sample_count(self) -> int:
        return len(self.rows)

    @property
    def estimated_count(self) -> int:
        return sum(row.status is GisProfileRowStatus.ESTIMATED for row in self.rows)

    @property
    def missing_count(self) -> int:
        return sum(row.status is GisProfileRowStatus.MISSING_SOURCE for row in self.rows)

    @property
    def invalid_count(self) -> int:
        return sum(row.status is GisProfileRowStatus.INVALID_MEASUREMENT for row in self.rows)


def create_gis_reference_calibration(
    dataset: Dataset, *, method_id: str, curve_key: str,
    calibration_id: str, tool_id: str, reviewer: str, applicability_reference: str,
    md_top_m: float, md_base_m: float, parameters: Mapping[str, float],
) -> GisReferenceCalibration:
    """Bind explicit parameters/evidence to the current source and metre-MD scope."""
    source = review_gis_reference_input(dataset, method_id=method_id, curve_key=curve_key)
    if not source.ready_for_calibration:
        raise ValueError("GIS source review failed: " + ", ".join(source.issues))
    bounds = (_finite(md_top_m), _finite(md_base_m))
    if bounds[0] > bounds[1]:
        raise ValueError("Calibration MD bounds must be ordered")
    assert source.curve is not None and source.curve.sample_md_bounds is not None
    observed = source.curve.sample_md_bounds
    if bounds[0] < observed[0] or bounds[1] > observed[1]:
        raise ValueError("Calibration MD scope exceeds source sample bounds")
    if not isinstance(parameters, Mapping) or set(parameters) != _PARAMETERS[method_id]:
        raise ValueError("Exact method calibration parameters are required")
    normalized = {key: _finite(value) for key, value in parameters.items()}
    # Delegate physical parameter constraints to the existing scalar methods.
    reference_key = "clean_reference_api" if method_id == "igr-linear-1" else "matrix_density_g_cm3"
    _estimate(method_id, normalized, normalized[reference_key])
    return GisReferenceCalibration(
        calibration_id=_text(calibration_id), tool_id=_text(tool_id),
        reviewer=_text(reviewer), applicability_reference=_text(applicability_reference),
        md_bounds=bounds, parameters=tuple(sorted(normalized.items())), source=source,
        _axis_signature=_axis_source_signature(dataset.active_index),
        _depths=ref(dataset.active_index.values), _values=ref(dataset.curves[curve_key].values),
        _depth_sha256=_array_digest(dataset.active_index.values),
        _values_sha256=_array_digest(dataset.curves[curve_key].values),
    )


def evaluate_gis_reference_sample(
    dataset: Dataset, calibration: GisReferenceCalibration, *, sample_index: int,
) -> CalibratedGisSample:
    """Recheck the source, then evaluate exactly one row without interpolation.

    The original array identities, MD coordinates and curve values are checked
    even if a caller edits samples in place without incrementing curve.version.
    Replaced arrays and reopened datasets require a new calibration even when
    copied IDs/versions match. Results retain their immutable calibration context.
    """
    validate_gis_reference_calibration(dataset, calibration)
    source = calibration.source
    depths = dataset.active_index.values
    values = dataset.curves[source.curve_key].values
    if type(sample_index) is not int or not 0 <= sample_index < len(depths):
        raise ValueError("A valid integer source sample index is required")
    md, value = _finite(depths[sample_index]), _finite(values[sample_index])
    if not calibration.md_bounds[0] <= md <= calibration.md_bounds[1]:
        raise ValueError("Source sample is outside calibration MD scope")
    estimate = _estimate(source.method_id, dict(calibration.parameters), value)
    return CalibratedGisSample(calibration, sample_index, md, value, estimate)


def evaluate_gis_reference_profile(
    dataset: Dataset, calibration: GisReferenceCalibration, *,
    md_top_m: float, md_base_m: float,
) -> CalibratedGisProfile:
    """Evaluate an explicit interval at original sample rows in source order.

    Validate the entire live calibration before and after calculation, not
    once per sample. Work on independent copies of the selected rows and
    reject a changed source rather than publish a partially stale profile.
    No interpolation, extrapolation, clipping, inferred parameters, derived
    curve insertion or continuous coverage estimate is performed.
    """
    validate_gis_reference_calibration(dataset, calibration)
    bounds = (_finite(md_top_m), _finite(md_base_m))
    if bounds[0] > bounds[1]:
        raise ValueError("Profile MD bounds must be ordered")
    if bounds[0] < calibration.md_bounds[0] or bounds[1] > calibration.md_bounds[1]:
        raise ValueError("Profile interval is outside calibration MD scope")
    source = calibration.source
    parameters = dict(calibration.parameters)
    # Reject an invalid calibration contract before treating individual bad
    # measurements as row-level QC. Never silently substitute parameters.
    if source.method_id not in _PARAMETERS or set(parameters) != _PARAMETERS[source.method_id]:
        raise ValueError("Exact method calibration parameters are required")
    reference_key = (
        "clean_reference_api" if source.method_id == "igr-linear-1" else "matrix_density_g_cm3"
    )
    _estimate(source.method_id, parameters, parameters[reference_key])
    depths = dataset.active_index.values
    values = dataset.curves[source.curve_key].values
    # The validated metre-MD axis is strictly monotonic. Search its ascending
    # view without sorting/reindexing or allocating a full-axis boolean mask.
    if depths[0] <= depths[-1]:
        start = int(np.searchsorted(depths, bounds[0], side="left"))
        stop = int(np.searchsorted(depths, bounds[1], side="right"))
    else:
        ascending = depths[::-1]
        start = len(depths) - int(np.searchsorted(ascending, bounds[1], side="right"))
        stop = len(depths) - int(np.searchsorted(ascending, bounds[0], side="left"))
    selected_depths = depths[start:stop].copy()
    selected_values = values[start:stop].copy()
    rows: list[CalibratedGisProfileRow] = []
    for offset, (raw_md, raw_value) in enumerate(zip(selected_depths, selected_values, strict=True)):
        md = _finite(raw_md)
        index = start + offset
        if not calibration.md_bounds[0] <= md <= calibration.md_bounds[1] or not bounds[0] <= md <= bounds[1]:
            raise ValueError("Profile MD source changed during calculation")
        if not np.isfinite(raw_value):
            rows.append(CalibratedGisProfileRow(
                index, md, None, GisProfileRowStatus.MISSING_SOURCE, None, "nonfinite_source",
            ))
            continue
        value = _finite(raw_value)
        try:
            estimate = _estimate(source.method_id, parameters, value)
        except ValueError as exc:
            rows.append(CalibratedGisProfileRow(
                index, md, value, GisProfileRowStatus.INVALID_MEASUREMENT, None, str(exc),
            ))
            continue
        # Scalar QC is retained, including numerical results outside physical
        # or reference range. Those results are not clipped or marked usable.
        rows.append(CalibratedGisProfileRow(
            index, md, value, GisProfileRowStatus.ESTIMATED, estimate,
        ))
    validate_gis_reference_calibration(dataset, calibration)
    if (
        not np.array_equal(selected_depths, depths[start:stop], equal_nan=True)
        or not np.array_equal(selected_values, values[start:stop], equal_nan=True)
    ):
        raise ValueError("Profile source rows changed during calculation")
    return CalibratedGisProfile(calibration, bounds, tuple(rows))


def validate_gis_reference_calibration(
    dataset: Dataset, calibration: GisReferenceCalibration,
) -> None:
    """Recheck a live calibration without evaluating or selecting a source row."""
    if not isinstance(calibration, GisReferenceCalibration):
        raise ValueError("An existing GIS calibration is required")
    source = calibration.source
    current = review_gis_reference_input(
        dataset, method_id=source.method_id, curve_key=source.curve_key,
    )
    if not current.ready_for_calibration or current != source:
        raise ValueError("Calibration source is stale or no longer eligible")
    if calibration._axis_signature != _axis_source_signature(dataset.active_index):
        raise ValueError("Calibration MD axis evidence changed")
    depths = dataset.active_index.values
    values = dataset.curves[source.curve_key].values
    if calibration._depths() is not depths or calibration._values() is not values:
        raise ValueError("Calibration source arrays were replaced")
    if calibration._depth_sha256 != _array_digest(depths):
        raise ValueError("Calibration MD coordinates changed")
    if calibration._values_sha256 != _array_digest(values):
        raise ValueError("Calibration curve sample values changed")


def _estimate(method: str, parameters: dict[str, float], value: float) -> PetrophysicalEstimate:
    if method == "igr-linear-1":
        return gamma_ray_index(gamma_api=value, **parameters)
    return density_porosity(bulk_density_g_cm3=value, **parameters)


def _axis_source_signature(axis: DatasetIndex) -> AxisSourceSignature:
    """Bind the reviewed MD axis identity and evidence without copying samples."""
    return (
        axis.mnemonic, axis.index_type, axis.role, axis.unit,
        axis.confidence, axis.evidence,
    )


def _array_digest(samples: np.ndarray) -> str:
    # Raw bytes alone miss in-place dtype reinterpretation with unchanged storage.
    # Bind the numeric representation and shape to the sampled bytes.
    digest = sha256()
    digest.update(samples.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(str(samples.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(np.ascontiguousarray(samples).data)
    return digest.hexdigest()


def _finite(value: float) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("A finite numeric value is required")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("A finite numeric value is required") from error
    if not isfinite(result):
        raise ValueError("A finite numeric value is required")
    return result


def _text(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Calibration identity and applicability evidence are required")
    return value.strip()
