"""Explicit, in-memory confirmation of reviewed GIS and geology evidence.

The caller must rebuild the gas report using its current settings before
confirmation and again before handoff. This boundary checks the chosen gas
candidate, original GIS snapshot and measured geology, not a fluid diagnosis.
No report file or export approval is produced implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gis_interval_sample_review import (
    MAX_GIS_INTERVAL_CURVES, review_gis_source_interval_batch,
)
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot
from geoworkbench.services.hydrocarbon_interpretation_legacy import HydrocarbonInterpretationReport
from geoworkbench.services.interpretation_geology_evidence_export import (
    verified_session_geology_evidence,
)
from geoworkbench.services.interpretation_gis_interval_evidence import GasGeologyGisIntervalEvidence
from geoworkbench.services.interpretation_gis_interval_evidence_html import (
    geology_gis_interval_evidence_html,
)
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class ConfirmedGisGeologySelection:
    """One explicit approval bound to the original report and reviewed arrays."""

    report: HydrocarbonInterpretationReport
    source_key: tuple[object, ...]
    evidence: GasGeologyGisIntervalEvidence
    snapshot: GisIntervalSnapshot


def _verify_candidate(
    report: HydrocarbonInterpretationReport,
    current_report: HydrocarbonInterpretationReport,
    evidence: GasGeologyGisIntervalEvidence,
) -> None:
    geology = evidence.geology
    bounds = (geology.gas_top, geology.gas_bottom)
    if (
        current_report.dataset_id != report.dataset_id
        or current_report.depth_axis_id != report.depth_axis_id
        or current_report.depth_unit != report.depth_unit
        or current_report.threshold != report.threshold
        or current_report.report_profile != report.report_profile
        or current_report.analysis_depth_interval != report.analysis_depth_interval
    ):
        raise ValueError("Confirmed GIS evidence has a changed gas report source or settings")
    original = tuple(
        item for item in report.candidates
        if (item.top_depth, item.bottom_depth) == bounds
    )
    current = tuple(
        item for item in current_report.candidates
        if (item.top_depth, item.bottom_depth) == bounds
    )
    if len(original) != 1 or current != original:
        raise ValueError("Confirmed GIS evidence has a changed or ambiguous gas candidate")


def _verify_evidence(
    session: ProjectSession,
    report: HydrocarbonInterpretationReport,
    current_report: HydrocarbonInterpretationReport,
    evidence: GasGeologyGisIntervalEvidence,
    snapshot: GisIntervalSnapshot,
) -> None:
    if not isinstance(evidence, GasGeologyGisIntervalEvidence):
        raise ValueError("A reviewed combined evidence result is required")
    if not isinstance(snapshot, GisIntervalSnapshot):
        raise ValueError("The original GIS review snapshot is required")
    keys = tuple(item.curve_key for item in evidence.gis)
    if (
        not 1 <= len(keys) <= MAX_GIS_INTERVAL_CURVES
        or len(set(keys)) != len(keys)
        or keys != snapshot.keys
        or any(item.review is None or item.issues for item in evidence.gis)
        or not any(item.review is not None and item.review.finite_count > 0 for item in evidence.gis)
    ):
        raise ValueError("Confirmation requires explicitly reviewed GIS sources and measured values")
    if (
        snapshot.source is not session.current_dataset
        or snapshot.dataset_id != evidence.geology.dataset_id
        or snapshot.active_index_id != evidence.geology.depth_axis_id
        or not snapshot.matches(lambda: False)
    ):
        raise ValueError("Confirmed GIS evidence has changed source arrays or metadata")
    _verify_candidate(report, current_report, evidence)
    verified_session_geology_evidence(session, report, (evidence.geology,))
    # Do not trust a table with matching counts or bounds alone. Verify it
    # against the exact original snapshot, then check the live source again.
    observed = review_gis_source_interval_batch(
        snapshot.dataset, curve_keys=keys,
        top_md_m=evidence.geology.gas_top, bottom_md_m=evidence.geology.gas_bottom,
    )
    if observed != evidence.gis or not snapshot.matches(lambda: False):
        raise ValueError("Confirmed GIS evidence differs from the original reviewed source")
    verified_session_geology_evidence(session, report, (evidence.geology,))


def confirm_gis_geology_selection(
    session: ProjectSession,
    report: HydrocarbonInterpretationReport,
    current_report: HydrocarbonInterpretationReport,
    evidence: GasGeologyGisIntervalEvidence,
    snapshot: GisIntervalSnapshot,
    *,
    source_key: tuple[object, ...],
) -> ConfirmedGisGeologySelection:
    """Confirm only an explicit preview with its original numeric snapshot."""
    if not isinstance(source_key, tuple) or not source_key:
        raise ValueError("Confirmation requires an identified report source")
    _verify_evidence(session, report, current_report, evidence, snapshot)
    return ConfirmedGisGeologySelection(report, source_key, evidence, snapshot)


def verified_gis_geology_handoff(
    session: ProjectSession,
    report: HydrocarbonInterpretationReport,
    current_report: HydrocarbonInterpretationReport,
    selection: ConfirmedGisGeologySelection,
    *,
    source_key: tuple[object, ...],
) -> GasGeologyGisIntervalEvidence:
    """Reject changed reports, settings, geology and numeric GIS sources."""
    if (
        not isinstance(selection, ConfirmedGisGeologySelection)
        or selection.report is not report
        or not source_key or selection.source_key != source_key
    ):
        raise ValueError("Confirmed GIS evidence has a stale report or source key")
    _verify_evidence(session, report, current_report, selection.evidence, selection.snapshot)
    return selection.evidence


def confirmed_gis_geology_evidence_html(
    session: ProjectSession,
    report: HydrocarbonInterpretationReport,
    current_report: HydrocarbonInterpretationReport,
    selection: ConfirmedGisGeologySelection,
    language: AppLanguage,
    *,
    source_key: tuple[object, ...],
) -> str:
    """Render a verified HTML fragment; the report owner controls placement."""
    evidence = verified_gis_geology_handoff(
        session, report, current_report, selection, source_key=source_key,
    )
    return geology_gis_interval_evidence_html(evidence, language)


__all__ = [
    "ConfirmedGisGeologySelection",
    "confirm_gis_geology_selection",
    "verified_gis_geology_handoff",
    "confirmed_gis_geology_evidence_html",
]
