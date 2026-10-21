"""Read-only GIS source inventory before any petrophysical interpretation.

An empty issue list establishes only a reviewable input, never calibration,
tool applicability, valid saturation or alignment with another dataset.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from geoworkbench.domain.models import CalculationState, Dataset, DatasetKind
from geoworkbench.services.geology_depth_alignment import supports_saved_md_geology
from geoworkbench.services.uom_dictionary import QuantityClass, default_uom_dictionary


_FAMILIES = {
    "gamma_ray": QuantityClass.GAMMA_RAY,
    "sp": QuantityClass.ELECTRIC_POTENTIAL,
    "caliper": QuantityClass.LENGTH,
    "bulk_density": QuantityClass.MASS_DENSITY,
    "neutron": QuantityClass.VOLUME_FRACTION,
    "sonic": QuantityClass.SLOWNESS,
    "resistivity": QuantityClass.RESISTIVITY,
    "pef": QuantityClass.DIMENSIONLESS,
}


@dataclass(frozen=True, slots=True)
class GisCurveInput:
    curve_key: str
    curve_id: str
    source_dataset_id: str
    original_mnemonic: str
    canonical_mnemonic: str | None
    family: str | None
    semantic_confidence: float | None
    semantic_evidence: tuple[str, ...]
    unit: str | None
    provenance: str
    version: int
    finite_sample_count: int
    sample_md_bounds: tuple[float, float] | None
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GisInputInventory:
    dataset_id: str
    axis_id: str
    axis_unit: str | None
    axis_confidence: float
    axis_evidence: tuple[str, ...]
    axis_issues: tuple[str, ...]
    curves: tuple[GisCurveInput, ...]


def inventory_gis_inputs(dataset: Dataset) -> GisInputInventory:
    """Snapshot existing source evidence without resolving aliases or editing arrays.

    Counts and bounds describe actual paired samples, not continuous coverage.
    Unknown semantics and incompatible axes stay explicit; no unit conversion,
    interpolation, source replacement or cross-dataset MD/lag inference occurs.
    """
    axis = dataset.active_index
    axis_issues: list[str] = []
    if dataset.kind is not DatasetKind.GIS:
        axis_issues.append("dataset_not_gis")
    if not supports_saved_md_geology(dataset):
        axis_issues.append("unverified_metre_md_alignment")
    depths = np.asarray(axis.values)
    numeric_axis = depths.ndim == 1 and depths.dtype.kind in "fiu"
    finite_depths = np.isfinite(depths) if numeric_axis else np.zeros(0, dtype=bool)
    if not numeric_axis or not depths.size or not finite_depths.all():
        axis_issues.append("invalid_depth_samples")
    if numeric_axis and depths.size > 1 and finite_depths.all():
        # Compare adjacent source samples directly: integer diff may overflow.
        if not (np.all(depths[1:] > depths[:-1]) or np.all(depths[1:] < depths[:-1])):
            axis_issues.append("ambiguous_depth_order")

    uoms = default_uom_dictionary()
    rows: list[GisCurveInput] = []
    for key, curve in dataset.curves.items():
        metadata = curve.metadata
        binding = metadata.semantic
        issues: list[str] = []
        family = binding.family if binding is not None else None
        expected = _FAMILIES.get(family or "")
        if binding is None or not binding.resolved:
            issues.append("unverified_semantics")
        if expected is None:
            issues.append("unsupported_gis_family")
        elif binding is not None and binding.quantity_class is not expected:
            issues.append("semantic_quantity_conflict")
        resolved_unit = uoms.resolve(metadata.unit or "")
        if not resolved_unit.recognized:
            issues.append("unknown_unit")
        elif expected is not None and resolved_unit.quantity_class is not expected:
            issues.append("unit_quantity_conflict")
        if binding is not None and binding.source_uom != metadata.unit:
            # A persisted binding must not validate metadata edited since import.
            issues.append("semantic_unit_changed")
        if binding is not None and (
            binding.source_mnemonic != metadata.original_mnemonic
            or binding.canonical_mnemonic != metadata.canonical_mnemonic
        ):
            issues.append("semantic_mnemonic_changed")
        if not metadata.source_dataset_id.strip() or not metadata.provenance.strip():
            issues.append("missing_source_provenance")
        if curve.state is not CalculationState.CURRENT:
            issues.append("curve_not_current")

        values = np.asarray(curve.values)
        paired = (
            numeric_axis and values.ndim == 1 and values.dtype.kind in "fiu"
            and values.shape == depths.shape
        )
        valid = finite_depths & np.isfinite(values) if paired else np.zeros(0, dtype=bool)
        count = int(np.count_nonzero(valid))
        bounds = None
        if not paired:
            issues.append("invalid_curve_samples")
        elif not count:
            issues.append("no_finite_paired_samples")
        elif not axis_issues:
            observed_depths = depths[valid]
            bounds = (float(np.min(observed_depths)), float(np.max(observed_depths)))
        rows.append(GisCurveInput(
            curve_key=key,
            curve_id=metadata.curve_id,
            source_dataset_id=metadata.source_dataset_id,
            original_mnemonic=metadata.original_mnemonic,
            canonical_mnemonic=binding.canonical_mnemonic if binding is not None else None,
            family=family,
            semantic_confidence=binding.confidence if binding is not None else None,
            semantic_evidence=tuple(binding.evidence) if binding is not None else (),
            unit=metadata.unit,
            provenance=metadata.provenance,
            version=curve.version,
            finite_sample_count=count,
            sample_md_bounds=bounds,
            issues=tuple(issues),
        ))
    return GisInputInventory(
        dataset_id=dataset.dataset_id,
        axis_id=axis.index_id,
        axis_unit=axis.unit,
        axis_confidence=axis.confidence,
        axis_evidence=tuple(axis.evidence),
        axis_issues=tuple(axis_issues),
        curves=tuple(rows),
    )
