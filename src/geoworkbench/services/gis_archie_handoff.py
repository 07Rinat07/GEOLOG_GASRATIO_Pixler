"""Immutable, fail-closed source seal for an explicit future Archie tablet handoff.

This does NOT display Sw on a tablet. The caller must additionally verify the
active project, well, dataset, viewport and layout at the UI boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind
from geoworkbench.services.gis_archie_profile import (
    ARCHIE_PROFILE_METHOD_ID, ArchieProfile, ArchieRowStatus,
)
from geoworkbench.services.gis_archie_source_profile import _axis_signature, _digest
from geoworkbench.services.gis_input_inventory import inventory_gis_inputs


def _live_signature(
    dataset: Dataset, porosity_curve_key: str, resistivity_curve_key: str,
) -> tuple[object, ...]:
    """Full-array and identity signature; no nearest-row or cross-dataset join."""
    axis = dataset.active_index
    phi = dataset.curves[porosity_curve_key]
    rt = dataset.curves[resistivity_curve_key]
    return (
        id(dataset), dataset.dataset_id, dataset.kind, dataset.active_index_id,
        id(axis), _axis_signature(dataset), id(axis.values), _digest(axis.values),
        porosity_curve_key, id(phi), phi.metadata, phi.version, phi.state,
        id(phi.values), _digest(phi.values),
        resistivity_curve_key, id(rt), rt.metadata, rt.version, rt.state,
        id(rt.values), _digest(rt.values),
        inventory_gis_inputs(dataset),
    )


@dataclass(frozen=True, slots=True, eq=False)
class ArchieTabletSourceSeal:
    """Reviewed exact-row Sw plus sealed live sources; not a saved interpretation."""

    dataset: Dataset
    profile: ArchieProfile
    porosity_curve_key: str
    resistivity_curve_key: str
    row_index: int
    axis_id: str
    signature: tuple[object, ...]

    def is_current(self, dataset: Dataset) -> bool:
        """Fail closed on any source/axis identity, metadata, version or byte edit."""
        if dataset is not self.dataset or dataset.active_index_id != self.axis_id:
            return False
        try:
            if _live_signature(
                dataset, self.porosity_curve_key, self.resistivity_curve_key
            ) != self.signature:
                return False
            selected = self.profile.rows[self.row_index]
            depth = dataset.active_index.values
            return (
                0 <= selected.sample_index < len(depth)
                and float(depth[selected.sample_index]) == selected.md_m
            )
        except (IndexError, KeyError, TypeError, ValueError, OverflowError, AttributeError):
            return False


def seal_archie_tablet_source(
    dataset: Dataset,
    profile: ArchieProfile, *,
    porosity_curve_key: str,
    resistivity_curve_key: str,
    row_index: int,
) -> ArchieTabletSourceSeal:
    """Bind one *existing* reviewed Archie profile to its exact live GIS rows.

    The original calculation must have come from the independently validated
    GIS Archie source adapter. This guard checks the available model metadata,
    all row depths, computed input provenance and source fingerprint. It does
    not accept input text as proof of physical reservoir-model applicability.
    """
    if (
        dataset.kind is not DatasetKind.GIS or not isinstance(profile, ArchieProfile)
        or profile.method_id != ARCHIE_PROFILE_METHOD_ID
        or not isinstance(porosity_curve_key, str)
        or not isinstance(resistivity_curve_key, str)
        or porosity_curve_key == resistivity_curve_key
        or type(row_index) is not int or not 0 <= row_index < len(profile.rows)
        or not all(isinstance(s, str) and s.strip() for s in (
            profile.reviewer, profile.applicability_reference, profile.porosity_source,
            profile.resistivity_source, profile.water_resistivity_reference,
            profile.alignment_reference,
        ))
    ):
        raise ValueError("Explicit reviewed Archie source and row required")
    try:
        before = _live_signature(dataset, porosity_curve_key, resistivity_curve_key)
        inventory = inventory_gis_inputs(dataset)
        curves = {entry.curve_key: entry for entry in inventory.curves}
        phi_info = curves[porosity_curve_key]
        rt_info = curves[resistivity_curve_key]
        if (
            inventory.axis_issues or phi_info.issues or rt_info.issues
            or phi_info.family != "neutron" or rt_info.family != "resistivity"
            or phi_info.unit != "v/v" or rt_info.unit != "ohm.m"
            or phi_info.source_dataset_id != rt_info.source_dataset_id
            or phi_info.curve_id == rt_info.curve_id
            or not profile.porosity_source.startswith(
                porosity_curve_key + ":" + phi_info.curve_id + " / "
            )
            or not profile.resistivity_source.startswith(
                resistivity_curve_key + ":" + rt_info.curve_id + " / "
            )
        ):
            raise ValueError("Ineligible or mismatched Archie input sources")
        depths = dataset.active_index.values
        phi = dataset.curves[porosity_curve_key].values
        rt = dataset.curves[resistivity_curve_key].values
        last_index = -1
        for row in profile.rows:
            if (
                row.sample_index <= last_index or row.sample_index >= len(depths)
                or row.sample_index < 0
                or float(depths[row.sample_index]) != row.md_m
                or not profile.md_bounds[0] <= row.md_m <= profile.md_bounds[1]
            ):
                raise ValueError("Archie row is not an exact live MD source row")
            last_index = row.sample_index
            if row.status is ArchieRowStatus.ESTIMATED:
                if row.estimate is None:
                    raise ValueError("Missing computed Archie row")
                parameters = dict(row.estimate.parameters)
                if (
                    not isfinite(float(phi[row.sample_index]))
                    or not isfinite(float(rt[row.sample_index]))
                    or parameters.get("porosity_fraction") != float(phi[row.sample_index])
                    or parameters.get("true_resistivity_ohm_m") != float(rt[row.sample_index])
                ):
                    raise ValueError("Archie computed inputs no longer match the source row")
            elif row.estimate is not None:
                raise ValueError("Invalid or missing Archie row contains an estimate")
        after = _live_signature(dataset, porosity_curve_key, resistivity_curve_key)
        if before != after:
            raise ValueError("Archie sources changed while sealing")
        return ArchieTabletSourceSeal(
            dataset, profile, porosity_curve_key, resistivity_curve_key,
            row_index, dataset.active_index.index_id, after,
        )
    except (KeyError, IndexError, TypeError, OverflowError, AttributeError) as exc:
        raise ValueError("Cannot seal missing or incompatible Archie sources") from exc
