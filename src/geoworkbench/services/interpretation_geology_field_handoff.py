"""Source-bound operator confirmation for measured-field report HTML only.

This is an in-memory handoff contract, not a signed PDF, Word, Excel or print
export. No source data is changed and missing assays remain unmeasured.
"""

from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    HydrocarbonInterpretationReport,
)
from geoworkbench.services.interpretation_geology_evidence_export import (
    verified_session_geology_evidence,
)
from geoworkbench.services.interpretation_geology_interval_evidence import (
    EvidenceKind,
    GasGeologyIntervalEvidence,
)
from geoworkbench.services.interpretation_geology_interval_evidence_html import (
    selectable_geology_evidence_fields,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_geology_snapshot import build_report_geology_snapshot


@dataclass(frozen=True, slots=True)
class ConfirmedGeologyFieldSelection:
    """Immutable confirmation tied to one live report and source fingerprint."""

    report_identity: int
    source_key: tuple[object, ...]
    geology_sha256: str
    evidence: tuple[GasGeologyIntervalEvidence, ...]
    fields: tuple[tuple[EvidenceKind, str], ...]


def _validate_fields(fields: tuple[tuple[EvidenceKind, str], ...]) -> None:
    allowed = {field for _, field in selectable_geology_evidence_fields(AppLanguage.EN)}
    if (
        not isinstance(fields, tuple)
        or not fields
        or any(
            not isinstance(field, tuple)
            or len(field) != 2
            or not all(isinstance(value, str) for value in field)
            or field not in allowed
            for field in fields
        )
        or len(set(fields)) != len(fields)
    ):
        raise ValueError("HTML handoff requires unique schema-owned measured fields")


def confirm_geology_field_selection(
    session: ProjectSession,
    report: HydrocarbonInterpretationReport,
    evidence: tuple[GasGeologyIntervalEvidence, ...],
    fields: tuple[tuple[EvidenceKind, str], ...],
    *,
    source_key: tuple[object, ...],
) -> ConfirmedGeologyFieldSelection:
    """Confirm exactly observed fields against current report and well geology."""

    _validate_fields(fields)
    if not isinstance(source_key, tuple) or not source_key:
        raise ValueError("HTML handoff requires an identified report source")
    if not evidence:
        raise ValueError("HTML handoff requires selected measured geology evidence")
    verified_session_geology_evidence(session, report, evidence)
    snapshot = build_report_geology_snapshot(session)
    if not snapshot.verify():
        raise ValueError("HTML handoff requires a verified geology fingerprint")
    return ConfirmedGeologyFieldSelection(
        report_identity=id(report),
        source_key=source_key,
        geology_sha256=snapshot.geology_sha256,
        evidence=evidence,
        fields=fields,
    )


def verified_geology_field_html_handoff(
    session: ProjectSession,
    report: HydrocarbonInterpretationReport,
    selection: ConfirmedGeologyFieldSelection,
    *,
    source_key: tuple[object, ...],
) -> tuple[
    tuple[GasGeologyIntervalEvidence, ...],
    tuple[tuple[EvidenceKind, str], ...],
]:
    """Fail closed if any source, selection or report identity has changed."""

    if (
        not isinstance(selection, ConfirmedGeologyFieldSelection)
        or selection.report_identity != id(report)
        or selection.source_key != source_key
        or not selection.geology_sha256
        or build_report_geology_snapshot(session).geology_sha256
        != selection.geology_sha256
    ):
        raise ValueError("Confirmed measured fields have a stale report or geology source")
    _validate_fields(selection.fields)
    verified_session_geology_evidence(session, report, selection.evidence)
    return selection.evidence, selection.fields


def confirmed_geology_field_report_html(
    session: ProjectSession,
    report: HydrocarbonInterpretationReport,
    selection: ConfirmedGeologyFieldSelection,
    language: AppLanguage,
    *,
    source_key: tuple[object, ...],
) -> str:
    """Hand off only verified field evidence to the existing HTML renderer."""

    from geoworkbench.services.hydrocarbon_interpretation import (
        hydrocarbon_interpretation_html,
    )

    evidence, fields = verified_geology_field_html_handoff(
        session, report, selection, source_key=source_key,
    )
    return hydrocarbon_interpretation_html(
        report, language, geology_evidence=evidence, geology_fields=fields,
    )


__all__ = [
    "ConfirmedGeologyFieldSelection",
    "confirm_geology_field_selection",
    "confirmed_geology_field_report_html",
    "verified_geology_field_html_handoff",
]
