"""Fail-closed boundary for optionally publishing measured geology evidence.

The operator's selected immutable snapshot must belong to a gas candidate,
dataset and MD axis of the report. Signed exports additionally re-read the
current well observations: an old or foreign sample may never be signed.
"""

from __future__ import annotations

from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.interpretation_geology_interval_evidence import (
    GasGeologyIntervalEvidence,
    correlate_gas_interval_with_well_geology,
)


def verified_report_geology_evidence(
    report: HydrocarbonInterpretationReport,
    selected: tuple[GasGeologyIntervalEvidence, ...],
) -> tuple[GasGeologyIntervalEvidence, ...]:
    """Require exact source identity and an existing gas candidate per item."""

    if not selected:
        return ()
    if report.depth_unit.strip().casefold() not in {"m", "meter", "metre", "meters", "metres"}:
        raise ValueError("Measured geology evidence requires a metre MD gas report")
    if not report.depth_axis_id:
        raise ValueError("Measured geology evidence requires an identified MD axis")
    candidates = {(item.top_depth, item.bottom_depth) for item in report.candidates}
    seen: set[tuple[float, float]] = set()
    for item in selected:
        interval = (item.gas_top, item.gas_bottom)
        if (
            item.dataset_id != report.dataset_id
            or item.depth_axis_id != report.depth_axis_id
            or item.depth_unit != "m"
            or interval not in candidates
            or interval in seen
        ):
            raise ValueError("Measured geology evidence has a foreign or stale gas source")
        seen.add(interval)
    return selected


def verified_session_geology_evidence(
    session: ProjectSession,
    report: HydrocarbonInterpretationReport,
    selected: tuple[GasGeologyIntervalEvidence, ...],
) -> tuple[GasGeologyIntervalEvidence, ...]:
    """Recompute *observations*, not a new gas interpretation, before signing.

    The service's immutable equality compares source IDs, record values,
    intervals, MD axis, well and missing-kind coverage. A source edit makes
    an older snapshot fail before any PDF or Report Passport is committed.
    """

    verified = verified_report_geology_evidence(report, selected)
    if not verified:
        return ()
    dataset, well = session.current_dataset, session.current_well
    if (
        dataset is None or well is None
        or dataset.dataset_id != report.dataset_id
        or dataset.active_index_id != report.depth_axis_id
    ):
        raise ValueError("Measured geology evidence has a different active source")
    for item in verified:
        if item.well_id != well.well_id:
            raise ValueError("Measured geology evidence belongs to a different well")
        observed = correlate_gas_interval_with_well_geology(
            session, top_depth=item.gas_top, bottom_depth=item.gas_bottom,
        )
        if observed != item:
            raise ValueError("Measured geology evidence changed after operator selection")
    return verified


__all__ = [
    "verified_report_geology_evidence",
    "verified_session_geology_evidence",
]
