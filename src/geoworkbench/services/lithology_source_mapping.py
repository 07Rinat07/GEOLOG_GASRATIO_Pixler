"""Explicit session-local review of saved lithology; never infer rock from names."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json

import numpy as np

from geoworkbench.project.session import ProjectSession
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.services.geology_depth_alignment import supports_saved_md_geology
from geoworkbench.services.gis_gti_lithology_screening import (
    LithologyObservation, ObservationQuality, RockFamily,
    review_gis_gti_lithology_intervals,
)


@dataclass(frozen=True, slots=True)
class LithologySource:
    well_id: str
    dataset_id: str
    depth_axis_id: str
    interval_id: str
    lithotype_id: str
    top_md_m: float
    bottom_md_m: float
    source_sha256: str
    axis_sha256: str


@dataclass(frozen=True, slots=True)
class ReviewedLithologyMapping:
    source: LithologySource
    mapping_id: str
    reviewer: str
    applicability_reference: str
    rock_family: RockFamily
    quality: ObservationQuality


def review_lithology_source(session: ProjectSession, *, interval_id: str) -> LithologySource:
    """Read one unambiguous saved interval on the current verified metre MD axis."""
    _required_text(interval_id)
    well, dataset = session.current_well, session.current_dataset
    if well is None or dataset is None or not supports_saved_md_geology(dataset):
        raise ValueError("A selected well and verified metre MD dataset are required")
    matches = [item for item in well.lithology if item.interval_id == interval_id]
    if len(matches) != 1:
        raise ValueError("Lithology source must exist with a unique interval ID")
    item = matches[0]
    _required_text(item.lithotype_id)
    catalog = {record.lithotype_id: record
               for record in LithotypeCatalogController(session).available()}
    if item.lithotype_id not in catalog:
        raise ValueError("Lithology source requires a known catalog lithotype")
    axis = dataset.active_index
    depth = np.asarray(axis.values, dtype=float)
    if (depth.ndim != 1 or depth.size < 2 or not np.isfinite(depth).all()
            or not np.all(np.diff(depth) > 0)):
        raise ValueError("MD axis must contain finite strictly increasing depths")
    # Reuse screening's public input contract; reversed bounds must not be normalized.
    observation = LithologyObservation(
        interval_id, axis.index_id, item.top_depth, item.bottom_depth,
        RockFamily.UNKNOWN_OR_MIXED, ObservationQuality.SUSPECT,
    )
    review_gis_gti_lithology_intervals(
        top_md_m=item.top_depth, bottom_md_m=item.bottom_depth,
        depth_axis_id=axis.index_id, observations=(), lithology=(observation,),
    )
    if item.top_depth < depth[0] or item.bottom_depth > depth[-1]:
        raise ValueError("Lithology source is outside the measured MD axis")
    # Include descriptions and translations: edits invalidate the expert's review.
    source_json = json.dumps(
        (asdict(item), asdict(catalog[item.lithotype_id])),
        sort_keys=True, ensure_ascii=True, allow_nan=False,
    )
    return LithologySource(
        well.well_id, dataset.dataset_id, axis.index_id, interval_id, item.lithotype_id,
        float(item.top_depth), float(item.bottom_depth),
        sha256(source_json.encode("utf-8")).hexdigest(),
        sha256(depth.tobytes()).hexdigest(),
    )


def create_lithology_mapping(
    session: ProjectSession, source: LithologySource, *, mapping_id: str,
    reviewer: str, applicability_reference: str, rock_family: RockFamily,
    quality: ObservationQuality,
) -> ReviewedLithologyMapping:
    """Record an explicit expert assertion, without proving field applicability."""
    if not isinstance(source, LithologySource):
        raise TypeError("A reviewed lithology source is required")
    if review_lithology_source(session, interval_id=source.interval_id) != source:
        raise ValueError("Lithology source changed; review it again")
    for text in (mapping_id, reviewer, applicability_reference):
        _required_text(text)
    if not isinstance(rock_family, RockFamily) or not isinstance(quality, ObservationQuality):
        raise TypeError("Rock family and quality must be explicit")
    return ReviewedLithologyMapping(
        source, mapping_id, reviewer, applicability_reference, rock_family, quality,
    )


def evaluate_lithology_mapping(
    session: ProjectSession, mapping: ReviewedLithologyMapping,
) -> LithologyObservation:
    """Recheck source freshness each time before emitting screening evidence."""
    if not isinstance(mapping, ReviewedLithologyMapping):
        raise TypeError("An explicit reviewed mapping is required")
    checked = create_lithology_mapping(
        session, mapping.source, mapping_id=mapping.mapping_id, reviewer=mapping.reviewer,
        applicability_reference=mapping.applicability_reference,
        rock_family=mapping.rock_family, quality=mapping.quality,
    )
    source = checked.source
    return LithologyObservation(
        source.interval_id, source.depth_axis_id, source.top_md_m, source.bottom_md_m,
        checked.rock_family, checked.quality,
    )


def _required_text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Explicit non-empty source and review identifiers are required")
