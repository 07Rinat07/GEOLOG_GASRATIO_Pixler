"""Source-bound GIS point evidence alongside measured well geology in one MD window.

Data-only INTERP-GIS-01 increment. The caller selects an interval and explicit
curve keys from the current dataset. This never aligns another dataset, fills
missing values, assigns a rock/fluid interpretation or computes saturation.
"""

from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gis_interval_sample_review import (
    MAX_GIS_INTERVAL_CURVES, GisSourceIntervalBatchItem,
    review_gis_source_interval_batch,
)
from geoworkbench.services.gis_interval_snapshot import (
    GisIntervalSnapshot, GisIntervalSourceChanged,
)
from geoworkbench.services.interpretation_geology_interval_evidence import (
    GasGeologyIntervalEvidence, correlate_gas_interval_with_well_geology,
)


@dataclass(frozen=True, slots=True)
class GasGeologyGisIntervalEvidence:
    """Separate measured geology and source GIS observations on one metre-MD axis.

    Geology coverage describes unions of observed intervals; GIS counts describe
    discrete source rows. They are deliberately not combined into a coverage
    fraction or assigned to individual lithotypes. No selected GIS means an
    empty tuple; a requested but invalid source remains an explicit blocked row.
    """

    geology: GasGeologyIntervalEvidence
    gis: tuple[GisSourceIntervalBatchItem, ...] = ()


def review_gas_geology_gis_interval(
    session: ProjectSession, *,
    top_depth: float,
    bottom_depth: float,
    curve_keys: tuple[str, ...] = (),
) -> GasGeologyGisIntervalEvidence:
    """Build fresh, read-only evidence for an explicitly requested MD interval.

    Use the current well/dataset only, with existing geology validation and GIS
    inventory rules (including exact-row external LAS provenance). Preserve
    the selected curve order and original source units, and report missing
    samples separately from blocked sources. No channel is inferred or selected
    automatically. The caller must rebuild this evidence after source changes;
    it is not an approval or proof of physical alignment between separate runs.
    """
    if (
        not isinstance(curve_keys, tuple)
        or len(curve_keys) > MAX_GIS_INTERVAL_CURVES
        or any(not isinstance(key, str) or not key.strip() for key in curve_keys)
        or len(set(curve_keys)) != len(curve_keys)
    ):
        raise ValueError("Select zero to eight unique GIS curve keys")

    dataset, well = session.current_dataset, session.current_well
    if dataset is None or well is None:
        raise ValueError("A selected well and dataset are required")

    if not curve_keys:
        return GasGeologyGisIntervalEvidence(
            correlate_gas_interval_with_well_geology(
                session, top_depth=top_depth, bottom_depth=bottom_depth,
            ),
        )

    # Capture the selected sources before building the geology and GIS evidence.
    # The source is checked again after both reviews; a changed dataset/axis or
    # in-place selected-curve edit must not yield a combined result.
    snapshot = GisIntervalSnapshot(dataset, curve_keys, lambda: False)
    geology = correlate_gas_interval_with_well_geology(
        session, top_depth=top_depth, bottom_depth=bottom_depth,
    )
    if (
        session.current_dataset is not dataset or session.current_well is not well
        or geology.well_id != well.well_id
        or geology.dataset_id != snapshot.dataset_id
        or geology.depth_axis_id != snapshot.active_index_id
    ):
        raise GisIntervalSourceChanged("GIS and geology source selection changed")

    gis = review_gis_source_interval_batch(
        snapshot.dataset, curve_keys=curve_keys,
        top_md_m=geology.gas_top, bottom_md_m=geology.gas_bottom,
    )
    if (
        session.current_dataset is not dataset or session.current_well is not well
        or not snapshot.matches(lambda: False)
    ):
        raise GisIntervalSourceChanged("GIS source changed during combined interval review")
    return GasGeologyGisIntervalEvidence(geology, gis)
