"""Session-local, explicitly reviewed calibration for one actual GIS sample.

Applicability text records the caller's expert evidence; it is not an automatic
certification of a tool or reservoir. No persistence or source mutations occur.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from weakref import ReferenceType, ref

import numpy as np

from geoworkbench.domain.models import Dataset
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


@dataclass(frozen=True, slots=True)
class GisReferenceCalibration:
    calibration_id: str
    tool_id: str
    reviewer: str
    applicability_reference: str
    md_bounds: tuple[float, float]
    parameters: tuple[tuple[str, float], ...]
    source: GisReferenceInputReview
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
    source = calibration.source
    current = review_gis_reference_input(
        dataset, method_id=source.method_id, curve_key=source.curve_key,
    )
    if not current.ready_for_calibration or current != source:
        raise ValueError("Calibration source is stale or no longer eligible")
    depths = dataset.active_index.values
    values = dataset.curves[source.curve_key].values
    if calibration._depths() is not depths or calibration._values() is not values:
        raise ValueError("Calibration source arrays were replaced")
    if calibration._depth_sha256 != _array_digest(depths):
        raise ValueError("Calibration MD coordinates changed")
    if calibration._values_sha256 != _array_digest(values):
        raise ValueError("Calibration curve sample values changed")
    if type(sample_index) is not int or not 0 <= sample_index < len(depths):
        raise ValueError("A valid integer source sample index is required")
    md, value = _finite(depths[sample_index]), _finite(values[sample_index])
    if not calibration.md_bounds[0] <= md <= calibration.md_bounds[1]:
        raise ValueError("Source sample is outside calibration MD scope")
    estimate = _estimate(source.method_id, dict(calibration.parameters), value)
    return CalibratedGisSample(calibration, sample_index, md, value, estimate)


def _estimate(method: str, parameters: dict[str, float], value: float) -> PetrophysicalEstimate:
    if method == "igr-linear-1":
        return gamma_ray_index(gamma_api=value, **parameters)
    return density_porosity(bulk_density_g_cm3=value, **parameters)


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
