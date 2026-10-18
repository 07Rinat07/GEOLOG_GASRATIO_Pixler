"""Measured MD interval intersections between gas and well geology.

First INTERP-GEO-01 data-only slice. Does not label fluid, create missing
samples, reinterpret LBA, resample curves, or modify imported LAS/project data.
Well geology currently stores measured-depth boundaries without an axis ID:
refuse TVD/TVDSS/time/uncertain-unit inputs instead of silently correlating.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

import numpy as np

from geoworkbench.domain.models import IndexRole, IndexType
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.report_geology_snapshot import build_report_geology_snapshot


EvidenceKind = Literal["lithology", "cuttings", "lba", "calcimetry", "stratigraphy"]
_KINDS: tuple[EvidenceKind, ...] = (
    "lithology", "cuttings", "lba", "calcimetry", "stratigraphy",
)
_NumberOrText = str | int | float


@dataclass(frozen=True, slots=True)
class MeasuredGeologyIntersection:
    """Observed source record overlapping one requested gas interval."""

    kind: EvidenceKind
    source_id: str
    source_top: float
    source_bottom: float
    overlap_top: float
    overlap_bottom: float
    overlap_fraction: float
    attributes: tuple[tuple[str, _NumberOrText], ...]

    @property
    def overlap_depth(self) -> float:
        return self.overlap_bottom - self.overlap_top


@dataclass(frozen=True, slots=True)
class GasGeologyIntervalEvidence:
    well_id: str
    dataset_id: str
    depth_axis_id: str
    gas_top: float
    gas_bottom: float
    depth_unit: str
    intersections: tuple[MeasuredGeologyIntersection, ...]
    coverage_by_kind: tuple[tuple[EvidenceKind, float], ...]
    missing_kinds: tuple[EvidenceKind, ...]

    def coverage(self, kind: EvidenceKind) -> float:
        return dict(self.coverage_by_kind)[kind]


def correlate_gas_interval_with_well_geology(
    session: ProjectSession,
    *,
    top_depth: float,
    bottom_depth: float,
) -> GasGeologyIntervalEvidence:
    """Return observed intersections and independent per-kind depth coverage.

    Only a verified active MD axis expressed in metres may intersect stored
    well geology. Intersections use positive lengths, not touching endpoints;
    overlapping source records count once in *coverage*, while every original
    source ID remains independently auditable. Zero carbonate measurements
    remain measurements. No data means unknown, never "negative".
    """

    dataset, well = session.current_dataset, session.current_well
    if dataset is None or well is None:
        raise ValueError("A selected well and dataset are required")
    axis = dataset.active_index
    if (
        axis.role is not IndexRole.DEPTH
        or axis.index_type is not IndexType.MD
        or (axis.unit or "").strip().casefold() not in {"m", "meter", "metre", "meters", "metres"}
    ):
        raise ValueError("Geology correlation requires an explicit metre MD depth axis")

    top, bottom = float(top_depth), float(bottom_depth)
    if not (isfinite(top) and isfinite(bottom) and top < bottom):
        raise ValueError("Gas interval requires two increasing finite MD depths")
    depth = np.asarray(axis.values, dtype=float)
    finite = depth[np.isfinite(depth)]
    if finite.size < 2 or top < float(finite.min()) or bottom > float(finite.max()):
        raise ValueError("Gas interval is outside the measured MD axis")

    evidence: list[MeasuredGeologyIntersection] = []

    def add(
        kind: EvidenceKind,
        source_id: str,
        source_top: float,
        source_bottom: float,
        attributes: tuple[tuple[str, _NumberOrText], ...],
    ) -> None:
        low, high = float(source_top), float(source_bottom)
        if not (isfinite(low) and isfinite(high)) or low == high:
            return
        low, high = min(low, high), max(low, high)
        overlap_top, overlap_bottom = max(top, low), min(bottom, high)
        if overlap_top >= overlap_bottom:
            return
        evidence.append(MeasuredGeologyIntersection(
            kind, source_id, low, high, overlap_top, overlap_bottom,
            (overlap_bottom - overlap_top) / (bottom - top),
            attributes,
        ))

    frozen = build_report_geology_snapshot(session, interval=(top, bottom))
    if frozen.well_id != well.well_id or not frozen.verify():
        raise ValueError("Geology source snapshot is not valid for selected well")

    for interval in frozen.lithology:
        attrs: list[tuple[str, _NumberOrText]] = [("lithotype_id", interval.lithotype_id)]
        if interval.description:
            attrs.append(("description", interval.description))
        add("lithology", interval.interval_id, interval.top_depth, interval.bottom_depth, tuple(attrs))

    for sample in frozen.cuttings:
        components: tuple[tuple[str, _NumberOrText], ...] = tuple(
            (f"lithotype:{item.lithotype_id}", item.percentage)
            for item in sample.components
            if 0.0 <= item.percentage <= 100.0
        )
        if components or sample.description:
            cuttings_attrs = components + (
                (("description", sample.description),) if sample.description else ()
            )
            add("cuttings", sample.sample_id, sample.top_depth, sample.bottom_depth, cuttings_attrs)

        lba: list[tuple[str, _NumberOrText]] = []
        for name in (
            "lba_group", "lba_type_id", "lba_intensity", "lba_color",
            "lba_distribution", "lba_cut", "lba_description",
        ):
            value = getattr(sample, name)
            if value is not None and (not isinstance(value, str) or value.strip()):
                lba.append((name, value))
        if lba:
            add("lba", sample.sample_id, sample.top_depth, sample.bottom_depth, tuple(lba))

        carbonate: list[tuple[str, _NumberOrText]] = []
        for name in ("calcite_percent", "dolomite_percent", "total_carbonate_percent"):
            value = getattr(sample, name)
            if value is not None and isfinite(value) and 0.0 <= value <= 100.0:
                carbonate.append((name, value))
        if carbonate:
            add(
                "calcimetry", sample.sample_id, sample.top_depth,
                sample.bottom_depth, tuple(carbonate),
            )

    for stratum in well.stratigraphy:
        code = str(stratum.code).strip()
        if not code:
            continue
        stratigraphy_attrs: list[tuple[str, _NumberOrText]] = [("code", code)]
        if stratum.name and stratum.name.strip():
            stratigraphy_attrs.append(("name", stratum.name))
        if stratum.rank and stratum.rank.strip():
            stratigraphy_attrs.append(("rank", stratum.rank))
        add("stratigraphy", stratum.interval_id, stratum.top_depth, stratum.bottom_depth, tuple(stratigraphy_attrs))

    intersections = tuple(sorted(
        evidence, key=lambda value: (
            value.overlap_top, value.overlap_bottom, _KINDS.index(value.kind), value.source_id,
        ),
    ))
    coverage = tuple(
        (kind, _union_coverage(
            ((item.overlap_top, item.overlap_bottom) for item in intersections if item.kind == kind),
            bottom - top,
        ))
        for kind in _KINDS
    )
    return GasGeologyIntervalEvidence(
        well_id=well.well_id,
        dataset_id=dataset.dataset_id,
        depth_axis_id=axis.index_id,
        gas_top=top,
        gas_bottom=bottom,
        depth_unit="m",
        intersections=intersections,
        coverage_by_kind=coverage,
        missing_kinds=tuple(kind for kind, fraction in coverage if fraction == 0.0),
    )


def _union_coverage(intervals, target_length: float) -> float:
    ordered = sorted(intervals)
    if not ordered:
        return 0.0
    covered = 0.0
    left, right = ordered[0]
    for start, stop in ordered[1:]:
        if start > right:
            covered += right - left
            left, right = start, stop
        else:
            right = max(right, stop)
    covered += right - left
    return min(1.0, covered / target_length)


__all__ = [
    "GasGeologyIntervalEvidence",
    "MeasuredGeologyIntersection",
    "correlate_gas_interval_with_well_geology",
]
