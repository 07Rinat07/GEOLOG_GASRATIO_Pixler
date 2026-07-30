from __future__ import annotations

from dataclasses import replace

from geoworkbench.project.interpretation_calculation_controller import (
    NormalizedGasCalculationMode,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services import hydrocarbon_interpretation_legacy as _legacy
from geoworkbench.services import hydrocarbon_interpretation_modes as _modes
from geoworkbench.services.hydrocarbon_interpretation_modes import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
    InterpretationMethodStatus,
    ManualInterpretationInterval,
    candidate_evidence_summary,
    fluid_hypothesis_basis,
    fluid_hypothesis_label,
    hydrocarbon_interpretation_html,
)


_EXPLICIT_MODE_SESSIONS: set[int] = set()


def set_normalized_gas_report_mode(
    session: ProjectSession,
    mode: NormalizedGasCalculationMode | str,
) -> None:
    """Persist the UI-selected report mode for the active session."""

    _EXPLICIT_MODE_SESSIONS.add(id(session))
    _modes.set_normalized_gas_report_mode(session, mode)


def build_hydrocarbon_interpretation_report(
    session: ProjectSession,
    *,
    threshold: float = 3.0,
    normalized_gas_mode: NormalizedGasCalculationMode | str | None = None,
) -> HydrocarbonInterpretationReport:
    """Build a report while preserving the legacy API when no mode was selected."""

    if normalized_gas_mode is None and id(session) not in _EXPLICIT_MODE_SESSIONS:
        return _legacy.build_hydrocarbon_interpretation_report(
            session,
            threshold=threshold,
        )
    report = _modes.build_hydrocarbon_interpretation_report(
        session,
        threshold=threshold,
        normalized_gas_mode=normalized_gas_mode,
    )
    primary = report.primary_mnemonic
    if not primary:
        return report
    names = tuple(_strip_source_prefix(part) for part in primary.split(" | "))
    cleaned = " | ".join(dict.fromkeys(name for name in names if name))
    return report if cleaned == primary else replace(report, primary_mnemonic=cleaned)


def _strip_source_prefix(value: str) -> str:
    stripped = value.strip()
    for prefix in ("server: ", "local-calculation: "):
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped


__all__ = [
    "HydrocarbonCandidateInterval",
    "HydrocarbonInterpretationReport",
    "InterpretationMethodStatus",
    "ManualInterpretationInterval",
    "build_hydrocarbon_interpretation_report",
    "candidate_evidence_summary",
    "fluid_hypothesis_basis",
    "fluid_hypothesis_label",
    "hydrocarbon_interpretation_html",
    "set_normalized_gas_report_mode",
]
