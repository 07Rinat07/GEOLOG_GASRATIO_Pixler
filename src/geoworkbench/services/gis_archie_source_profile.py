"""Fail-closed read-only Archie input binding on one live, verified GIS MD axis.

This adapter never infers effective porosity or true formation resistivity from
a mnemonic. Operator evidence is required for both physical meanings and for
co-registration; it is not an automatic certification of model applicability.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from math import isfinite

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind
from geoworkbench.services.gis_archie_profile import (
    ArchieInputRow, ArchieProfile, evaluate_archie_rows,
)
from geoworkbench.services.gis_input_inventory import inventory_gis_inputs
from geoworkbench.services.uom_dictionary import default_uom_dictionary


def _digest(array: np.ndarray) -> str:
    """Bind dtype, shape and bytes: a same-byte dtype reinterpretation is stale."""
    digest = sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(str(array.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(np.ascontiguousarray(array).data)
    return digest.hexdigest()


def _axis_signature(dataset: Dataset) -> tuple[object, ...]:
    axis = dataset.active_index
    return (
        axis.index_id, axis.mnemonic, axis.index_type, axis.role, axis.unit,
        axis.confidence, axis.evidence, dataset.active_index_id,
    )


def evaluate_gis_archie_sources(
    dataset: Dataset, *,
    porosity_curve_key: str,
    resistivity_curve_key: str,
    reviewer: str,
    applicability_reference: str,
    effective_porosity_reference: str,
    true_resistivity_reference: str,
    alignment_reference: str,
    water_resistivity_reference: str,
    md_top_m: float,
    md_base_m: float,
    formation_water_resistivity_ohm_m: float,
    tortuosity_factor: float,
    cementation_exponent: float,
    saturation_exponent: float,
    max_rows: int = 10_000,
) -> ArchieProfile:
    """Evaluate manually validated phi/Rt from exact rows of one live GIS dataset.

    A clean metadata/inventory review alone does not make NPHI effective
    porosity or an arbitrary resistivity measurement Rt. Each is separately
    attested by the caller. Only existing v/v and ohm.m values are accepted;
    no percent conversion, cross-run join or interpolation is allowed.
    """
    evidence = (
        reviewer, applicability_reference, effective_porosity_reference,
        true_resistivity_reference, alignment_reference, water_resistivity_reference,
    )
    if any(not isinstance(item, str) or not item.strip() for item in evidence):
        raise ValueError("Explicit source, alignment and physical model evidence required")
    if (
        not isinstance(porosity_curve_key, str) or not porosity_curve_key.strip()
        or not isinstance(resistivity_curve_key, str) or not resistivity_curve_key.strip()
        or porosity_curve_key == resistivity_curve_key
    ):
        raise ValueError("Two distinct explicitly selected GIS curve keys required")
    if type(max_rows) is not int or max_rows < 1:
        raise ValueError("Positive integer row budget required")
    if dataset.kind is not DatasetKind.GIS:
        raise ValueError("Only a native GIS dataset is eligible; no implicit external alignment")
    if isinstance(md_top_m, (bool, np.bool_)) or isinstance(md_base_m, (bool, np.bool_)):
        raise ValueError("Finite ordered metre-MD bounds required")
    try:
        top, base = float(md_top_m), float(md_base_m)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Finite ordered metre-MD bounds required") from exc
    if not isfinite(top) or not isfinite(base) or top > base:
        raise ValueError("Finite ordered metre-MD bounds required")
    before = inventory_gis_inputs(dataset)
    if before.axis_issues:
        raise ValueError("GIS MD axis is ineligible: " + ", ".join(before.axis_issues))
    selected = {entry.curve_key: entry for entry in before.curves}
    if porosity_curve_key not in selected or resistivity_curve_key not in selected:
        raise ValueError("Selected source curve is unavailable")
    phi_info, rt_info = selected[porosity_curve_key], selected[resistivity_curve_key]
    if phi_info.issues or rt_info.issues:
        raise ValueError("Selected sources have unresolved GIS inventory issues")
    uoms = default_uom_dictionary()
    if (
        uoms.resolve(phi_info.unit or "").canonical != "v/v"
        or uoms.resolve(rt_info.unit or "").canonical != "ohm.m"
        or phi_info.family != "neutron" or rt_info.family != "resistivity"
    ):
        raise ValueError("Explicit volume-fraction and resistivity source semantics required")
    if (
        phi_info.curve_id == rt_info.curve_id
        or phi_info.source_dataset_id != rt_info.source_dataset_id
    ):
        raise ValueError("Sources must be distinct curves from the same source dataset")
    axis = dataset.active_index.values
    phi = dataset.curves[porosity_curve_key].values
    rt = dataset.curves[resistivity_curve_key].values
    # Full-array fingerprints detect edits even outside the requested interval.
    signature = _axis_signature(dataset)
    source_digests = (_digest(axis), _digest(phi), _digest(rt))
    if axis[0] <= axis[-1]:
        start = int(np.searchsorted(axis, top, side="left"))
        stop = int(np.searchsorted(axis, base, side="right"))
    else:
        ascending = axis[::-1]
        start = len(axis) - int(np.searchsorted(ascending, base, side="right"))
        stop = len(axis) - int(np.searchsorted(ascending, top, side="left"))
    if stop <= start:
        raise ValueError("No actual GIS rows inside requested MD interval")
    if stop - start > max_rows:
        raise ValueError("Selected interval exceeds row budget without truncation")
    depths = axis[start:stop].copy()
    porosities = phi[start:stop].copy()
    resistivities = rt[start:stop].copy()

    def source_value(value: float) -> float | None:
        raw = float(value)
        return raw if isfinite(raw) else None

    rows = tuple(
        ArchieInputRow(
            sample_index=start + offset, md_m=float(md),
            porosity_fraction=source_value(phi_value),
            true_resistivity_ohm_m=source_value(rt_value),
        )
        for offset, (md, phi_value, rt_value) in enumerate(
            zip(depths, porosities, resistivities, strict=True)
        )
    )
    result = evaluate_archie_rows(
        rows, reviewer=reviewer, applicability_reference=applicability_reference,
        porosity_source=f"{porosity_curve_key}:{phi_info.curve_id} / {effective_porosity_reference}",
        resistivity_source=f"{resistivity_curve_key}:{rt_info.curve_id} / {true_resistivity_reference}",
        water_resistivity_reference=water_resistivity_reference,
        formation_water_resistivity_ohm_m=formation_water_resistivity_ohm_m,
        tortuosity_factor=tortuosity_factor, cementation_exponent=cementation_exponent,
        saturation_exponent=saturation_exponent, max_rows=max_rows,
    )
    # Recheck metadata, provenance and actual bytes; fail rather than publish
    # a result from a source mutated while the computation was in progress.
    if (
        dataset.active_index.values is not axis
        or porosity_curve_key not in dataset.curves
        or resistivity_curve_key not in dataset.curves
        or dataset.curves[porosity_curve_key].values is not phi
        or dataset.curves[resistivity_curve_key].values is not rt
        or signature != _axis_signature(dataset)
        or source_digests != (_digest(axis), _digest(phi), _digest(rt))
        or before != inventory_gis_inputs(dataset)
    ):
        raise ValueError("Archie GIS sources changed during evaluation")
    return replace(result, alignment_reference=alignment_reference.strip())
