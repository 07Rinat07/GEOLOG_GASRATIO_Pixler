"""Read-only GIS source inventory before any petrophysical interpretation.

An empty issue list establishes only a reviewable input, never calibration,
tool applicability, valid saturation or alignment with another dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

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

GIS_SAMPLE_FAMILIES = frozenset(_FAMILIES)


def _unique_manifest_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate external LAS manifest field")
        result[key] = value
    return result


def exact_external_gis_curve_ids(dataset: Dataset) -> frozenset[str]:
    """Identify exact-row external curves backed by an unambiguous import manifest.

    This does not establish geological alignment or physical applicability.
    Resampled curves and records without matching provenance remain ineligible.
    """
    matches: dict[str, int] = {}
    curves_by_id = {curve.metadata.curve_id: curve for curve in dataset.curves.values()}
    duplicate_ids: set[str] = set()
    seen_ids: set[str] = set()
    for curve in dataset.curves.values():
        if curve.metadata.curve_id in seen_ids:
            duplicate_ids.add(curve.metadata.curve_id)
        seen_ids.add(curve.metadata.curve_id)
    for key, encoded in dataset.parameters.items():
        if (not key.startswith("EXTERNAL_LAS_IMPORT_") or not isinstance(encoded, str)
                or len(encoded) > 4_000_000):
            continue
        try:
            manifest = json.loads(encoded, object_pairs_hook=_unique_manifest_object)
        except (ValueError, RecursionError):
            continue
        if not isinstance(manifest, dict) or type(manifest.get("version")) is not int:
            continue
        digest, entries = manifest.get("source_sha256"), manifest.get("curves")
        if (manifest["version"] != 1 or manifest.get("mapping") != "exact"
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or not isinstance(entries, list)):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            curve_id, source_name, source_unit = (
                entry.get("target_curve_id"), entry.get("source_mnemonic"), entry.get("source_unit")
            )
            if (not isinstance(curve_id, str) or not curve_id.strip()
                    or not isinstance(source_name, str) or not source_name.strip()):
                continue
            if source_unit is not None and not isinstance(source_unit, str):
                continue
            candidate_curve = curves_by_id.get(curve_id)
            if candidate_curve is None or curve_id in duplicate_ids:
                continue
            metadata = candidate_curve.metadata
            if (metadata.semantic is None or metadata.semantic.family not in _FAMILIES
                    or metadata.source_dataset_id != dataset.dataset_id
                    or entry.get("target_mnemonic") != metadata.original_mnemonic
                    or source_unit != metadata.unit
                    or metadata.provenance != f"external-las:{digest}:{source_name}:{source_unit or ''}"):
                continue
            matches[curve_id] = matches.get(curve_id, 0) + 1
    return frozenset(curve_id for curve_id, count in matches.items() if count == 1)


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



_GIS_SCAN_CHUNK_ROWS = 65_536


def _inspect_depth_axis(depths: np.ndarray) -> tuple[bool, bool]:
    """Check every MD sample and adjacent pair without whole-axis masks."""
    all_finite = True
    ascending = True
    descending = True
    previous = None
    for start in range(0, len(depths), _GIS_SCAN_CHUNK_ROWS):
        part = depths[start:start + _GIS_SCAN_CHUNK_ROWS]
        all_finite = bool(np.isfinite(part).all()) and all_finite
        if previous is not None:
            ascending = ascending and bool(part[0] > previous)
            descending = descending and bool(part[0] < previous)
        if len(part) > 1:
            ascending = ascending and bool(np.all(part[1:] > part[:-1]))
            descending = descending and bool(np.all(part[1:] < part[:-1]))
        previous = part[-1]
    return all_finite, ascending or descending


def _paired_sample_stats(
    depths: np.ndarray, values: np.ndarray, *, allow_bounds: bool,
) -> tuple[int, tuple[float, float] | None]:
    """Count actual finite MD/value pairs and optionally calculate their extrema."""
    count = 0
    minimum = float("inf")
    maximum = float("-inf")
    for start in range(0, len(depths), _GIS_SCAN_CHUNK_ROWS):
        stop = min(start + _GIS_SCAN_CHUNK_ROWS, len(depths))
        chunk_depths = depths[start:stop]
        valid = np.isfinite(chunk_depths) & np.isfinite(values[start:stop])
        selected = int(np.count_nonzero(valid))
        count += selected
        if selected and allow_bounds:
            measured_depths = chunk_depths[valid]
            minimum = min(minimum, float(np.min(measured_depths)))
            maximum = max(maximum, float(np.max(measured_depths)))
    return count, ((minimum, maximum) if count and allow_bounds else None)


def inventory_gis_inputs(dataset: Dataset) -> GisInputInventory:
    """Snapshot existing source evidence without resolving aliases or editing arrays.

    Counts and bounds describe actual paired samples, not continuous coverage.
    Unknown semantics and incompatible axes stay explicit. Non-GIS datasets
    admit only individually verified exact-row external LAS insertions; no unit
    conversion, interpolation or cross-dataset MD/lag inference occurs here.
    """
    axis = dataset.active_index
    axis_issues: list[str] = []
    external_ids = exact_external_gis_curve_ids(dataset) if dataset.kind is not DatasetKind.GIS else frozenset()
    if dataset.kind is not DatasetKind.GIS and not external_ids:
        axis_issues.append("dataset_not_gis")
    if not supports_saved_md_geology(dataset):
        axis_issues.append("unverified_metre_md_alignment")
    depths = np.asarray(axis.values)
    numeric_axis = depths.ndim == 1 and depths.dtype.kind in "fiu"
    finite_axis, ordered_axis = (
        _inspect_depth_axis(depths) if numeric_axis and depths.size else (False, False)
    )
    if not finite_axis:
        axis_issues.append("invalid_depth_samples")
    if numeric_axis and depths.size > 1 and finite_axis and not ordered_axis:
        axis_issues.append("ambiguous_depth_order")

    uoms = default_uom_dictionary()
    rows: list[GisCurveInput] = []
    for key, curve in dataset.curves.items():
        metadata = curve.metadata
        binding = metadata.semantic
        issues: list[str] = []
        if dataset.kind is not DatasetKind.GIS and metadata.curve_id not in external_ids:
            issues.append("external_source_unverified")
        if not metadata.curve_id.strip():
            issues.append("missing_curve_id")
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
        count, bounds = (
            _paired_sample_stats(depths, values, allow_bounds=not axis_issues)
            if paired else (0, None)
        )
        if not paired:
            issues.append("invalid_curve_samples")
        elif not count:
            issues.append("no_finite_paired_samples")
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
