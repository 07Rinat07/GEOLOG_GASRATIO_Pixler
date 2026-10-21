"""Explicit source selection for calibration of existing reference methods.

This review does not establish tool applicability, calibration or continuous
coverage, and never authorizes a calculation using a saved, potentially stale review.
"""

from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_input_inventory import GisCurveInput, inventory_gis_inputs
from geoworkbench.services.uom_dictionary import default_uom_dictionary


_SOURCE_REQUIREMENTS = {
    "igr-linear-1": ("gamma_ray", "API"),
    "density-porosity-1": ("bulk_density", "g/cm3"),
}


@dataclass(frozen=True, slots=True)
class GisReferenceInputReview:
    method_id: str
    dataset_id: str
    axis_id: str
    curve_key: str
    required_unit: str
    curve: GisCurveInput | None
    issues: tuple[str, ...]

    @property
    def ready_for_calibration(self) -> bool:
        """Only source checks passed; physical applicability remains external."""
        return not self.issues


def review_gis_reference_input(
    dataset: Dataset, *, method_id: str, curve_key: str,
) -> GisReferenceInputReview:
    """Review one explicitly selected channel against a method's source contract.

    Rebuild the inventory on every call. Equivalent unit spellings are accepted,
    but different scales (even in the same quantity class) are not converted.
    No fallback channel, cross-run correlation or reference parameters are inferred.
    Archie has no source-selection contract here: effective porosity and validated
    true resistivity cannot be inferred from the broad neutron/resistivity families.
    """
    if not isinstance(method_id, str) or method_id not in _SOURCE_REQUIREMENTS:
        raise ValueError("Unsupported GIS reference source method")
    if not isinstance(curve_key, str) or not curve_key.strip():
        raise ValueError("An explicit curve key is required")
    family, unit = _SOURCE_REQUIREMENTS[method_id]
    inventory = inventory_gis_inputs(dataset)
    curve = next((row for row in inventory.curves if row.curve_key == curve_key), None)
    issues = [f"axis:{issue}" for issue in inventory.axis_issues]
    if curve is None:
        issues.append("curve_not_found")
    else:
        issues.extend(f"curve:{issue}" for issue in curve.issues)
        if curve.family != family:
            issues.append("method_family_mismatch")
        # Quantity compatibility alone does not make a scalar fit an equation.
        if default_uom_dictionary().resolve(curve.unit or "").canonical != unit:
            issues.append("method_unit_mismatch")
        if not curve.curve_id.strip():
            issues.append("missing_curve_id")
    return GisReferenceInputReview(
        method_id=method_id,
        dataset_id=inventory.dataset_id,
        axis_id=inventory.axis_id,
        curve_key=curve_key,
        required_unit=unit,
        curve=curve,
        issues=tuple(issues),
    )
