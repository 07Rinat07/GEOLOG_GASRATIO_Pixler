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

from geoworkbench.project.session import ProjectSession
from geoworkbench.services.geology_depth_alignment import supports_saved_md_geology
from geoworkbench.services.report_geology_snapshot import build_report_geology_snapshot
from geoworkbench.services.lba_observations import LBA_OBSERVATION_FIELDS


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

    def attribute_coverage(self, kind: EvidenceKind, attribute: str) -> float:
        """Observed fraction for one recorded field, not its entire evidence kind.

        A sample with measured calcite but no dolomite cannot imply dolomite
        coverage. Recorded zero values remain observations, and overlapping
        records count only once. An absent field has zero measured coverage.
        """
        if not isinstance(attribute, str) or not attribute.strip():
            raise ValueError("Evidence attribute name must be non-empty")
        # Reuse the verified MD bounds and per-observation interval guard.
        self.uncovered_intervals(kind)
        observed = (
            (item.overlap_top, item.overlap_bottom)
            for item in self.intersections
            if item.kind == kind
            and any(name == attribute for name, _ in item.attributes)
        )
        return _union_coverage(observed, self.gas_bottom - self.gas_top)

    def uncovered_intervals(self, kind: EvidenceKind) -> tuple[tuple[float, float], ...]:
        """Complement of observed depth union, never negative assay intervals."""

        if self.depth_unit != "m" or kind not in _KINDS or not (
            isfinite(self.gas_top) and isfinite(self.gas_bottom)
            and self.gas_top < self.gas_bottom
            and isfinite(self.gas_bottom - self.gas_top)
        ):
            raise ValueError("Uncovered intervals require a known kind and finite MD bounds")
        cursor = self.gas_top
        gaps: list[tuple[float, float]] = []
        for start, stop in sorted(
            (item.overlap_top, item.overlap_bottom)
            for item in self.intersections if item.kind == kind
        ):
            if not self.gas_top <= start < stop <= self.gas_bottom:
                raise ValueError("Evidence observation is outside the requested gas interval")
            if start > cursor:
                gaps.append((cursor, start))
            cursor = max(cursor, stop)
        if cursor < self.gas_bottom:
            gaps.append((cursor, self.gas_bottom))
        return tuple(gaps)


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
    if not supports_saved_md_geology(dataset):
        raise ValueError("Geology correlation requires an explicit metre MD depth axis with verified source alignment")

    # The requested gas interval is a measured MD selection, not an
    # untyped UI string or boolean. float(...) would silently accept both.
    # Check each scalar separately before any numeric coercion.
    selected_bounds = (np.asarray(top_depth), np.asarray(bottom_depth))
    if any(
        value.ndim != 0
        or value.dtype.kind not in "fiu"
        or not np.isfinite(value).all()
        for value in selected_bounds
    ):
        raise ValueError("Gas interval requires two increasing finite numeric MD depths")
    top, bottom = (float(value) for value in selected_bounds)
    # Finite endpoints can still overflow on subtraction. Coverage needs a
    # representable denominator, otherwise measured intervals become zero.
    if not (isfinite(top) and isfinite(bottom) and top < bottom and isfinite(bottom - top)):
        raise ValueError("Gas interval requires two increasing finite MD depths")
    depth = np.asarray(axis.values)
    # Filtering invalid coordinates would make a partly unreadable MD axis
    # appear eligible merely because its remaining min/max enclose the gas
    # interval. Never coerce text depths or silently discard source rows.
    if (
        depth.ndim != 1
        or depth.dtype.kind not in "fiu"
        or depth.size < 2
        or not np.isfinite(depth).all()
    ):
        raise ValueError("Geology correlation requires a one-dimensional finite numeric MD axis")
    if top < float(depth.min()) or bottom > float(depth.max()):
        raise ValueError("Gas interval is outside the measured MD axis")

    # The generic report snapshot skips malformed source intervals. Explicit
    # measured evidence must not silently turn a corrupt geological record
    # into an apparent gap or incomplete coverage. An invalid bound cannot
    # reliably be classified as inside or outside the requested gas interval.
    for source_kind, records in (
        ("lithology", well.lithology),
        ("cuttings", well.cuttings),
        ("stratigraphy", well.stratigraphy),
    ):
        for record in records:
            # Validate each source scalar before combining: NumPy would
            # otherwise coerce a boolean + float pair to a numeric array.
            try:
                bounds = (np.asarray(record.top_depth), np.asarray(record.bottom_depth))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Geology correlation requires finite numeric MD bounds in {source_kind}"
                ) from exc
            if any(
                bound.ndim != 0
                or bound.dtype.kind not in "fiu"
                or not np.isfinite(bound).all()
                for bound in bounds
            ):
                raise ValueError(
                    f"Geology correlation requires finite numeric MD bounds in {source_kind}"
                )

    # Explicit measured evidence must not silently discard malformed
    # components from the generic report snapshot or the 0..100 filter.
    for source_sample in well.cuttings:
        for component in source_sample.components:
            _validate_measured_percentage(component.percentage, "cuttings")
        # None means no assay; a present value must survive validation before
        # the generic snapshot can coerce it or discard it as missing.
        for field in ("calcite_percent", "dolomite_percent", "total_carbonate_percent"):
            value = getattr(source_sample, field)
            if value is not None:
                _validate_measured_percentage(value, "calcimetry")

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
        for name in LBA_OBSERVATION_FIELDS:
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
        # Coercion would turn absent or malformed data into an observation
        # such as "None" and falsely increase measured coverage.
        if not isinstance(stratum.code, str):
            raise ValueError("Geology correlation requires a text stratigraphy code")
        code = stratum.code.strip()
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


def _validate_measured_percentage(value: object, source: str) -> None:
    message = f"Geology correlation requires finite numeric {source} percentages from 0 to 100"
    try:
        fraction = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(message) from exc
    if (
        fraction.ndim != 0
        or fraction.dtype.kind not in "fiu"
        or not np.isfinite(fraction).all()
        or not 0.0 <= float(fraction) <= 100.0
    ):
        raise ValueError(message)


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
