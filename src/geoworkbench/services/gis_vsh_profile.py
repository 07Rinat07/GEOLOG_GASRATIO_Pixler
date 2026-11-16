"""Explicit linear GR shale-volume reference profile, never an implicit IGR alias.

The selected model assumes a linear local GR-to-shale-volume relationship.
Applicability evidence is an expert attestation, not a certification by code.
No source changes, interpolation, clipping, lithology or pay classification.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_reference_calibration import (
    CalibratedGisProfileRow,
    GisReferenceCalibration,
    evaluate_gis_reference_profile,
    validate_gis_reference_calibration,
)
from geoworkbench.services.petrophysical_reference_models import PetrophysicalEstimate


LINEAR_VSH_METHOD_ID = "vsh-gr-linear-1"


@dataclass(frozen=True, slots=True)
class GisVshProfile:
    """A distinct interpretation snapshot with source calibration and model evidence."""

    method_id: str
    calibration: GisReferenceCalibration
    reviewer: str
    applicability_reference: str
    md_bounds: tuple[float, float]
    rows: tuple[CalibratedGisProfileRow, ...]


def evaluate_gis_vsh_profile(
    dataset: Dataset,
    calibration: GisReferenceCalibration,
    *,
    method_id: str,
    reviewer: str,
    applicability_reference: str,
    md_top_m: float,
    md_base_m: float,
    max_rows: int | None = None,
) -> GisVshProfile:
    """Evaluate Vsh = IGR only under a separately selected linear model.

    The caller supplies local evidence that the GR response represents shale
    volume, rather than other radioactive minerals or unrelated facies effects.
    The existing IGR calibration supplies verified API endpoints and MD scope.
    Preserve original row identities, source values, missing/invalid states
    and out-of-reference QC; do not turn an inadmissible value into a fraction.
    """
    if method_id != LINEAR_VSH_METHOD_ID:
        raise ValueError("An explicit supported Vsh method is required")
    if (
        not isinstance(reviewer, str) or not reviewer.strip()
        or not isinstance(applicability_reference, str) or not applicability_reference.strip()
    ):
        raise ValueError("Separate Vsh reviewer and applicability evidence are required")
    if (
        not isinstance(calibration, GisReferenceCalibration)
        or calibration.source.method_id != "igr-linear-1"
    ):
        raise ValueError("Vsh requires an existing calibrated IGR source")
    igr = evaluate_gis_reference_profile(
        dataset, calibration, md_top_m=md_top_m, md_base_m=md_base_m,
        max_rows=max_rows,
    )
    rows: list[CalibratedGisProfileRow] = []
    for row in igr.rows:
        if row.estimate is None:
            rows.append(row)
            continue
        estimate = row.estimate
        vsh = PetrophysicalEstimate(
            LINEAR_VSH_METHOD_ID, estimate.value, estimate.unit, estimate.quality,
            estimate.parameters + (("igr", estimate.value),),
        )
        rows.append(replace(row, estimate=vsh))
    # The source may have changed during the separate interpretation stage.
    validate_gis_reference_calibration(dataset, calibration)
    return GisVshProfile(
        LINEAR_VSH_METHOD_ID, calibration, reviewer.strip(),
        applicability_reference.strip(), igr.md_bounds, tuple(rows),
    )
