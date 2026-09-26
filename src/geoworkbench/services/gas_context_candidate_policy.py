from __future__ import annotations

from dataclasses import replace

from geoworkbench.domain.gas_context_events import (
    GasContextEvent,
    GasContextRegistry,
    InterpretationImpact,
)
from geoworkbench.domain.models import DepthDomain
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
)


def apply_gas_context_to_report(
    report: HydrocarbonInterpretationReport,
    registry: GasContextRegistry,
    *,
    depth_domain: DepthDomain,
) -> HydrocarbonInterpretationReport:
    """Apply confirmed operator gas context to automatic interval classification.

    Calculated source curves and candidate metrics are never mutated. Contexts marked
    as technological/excluded suppress an automatic geological candidate from the
    prospective-interval list; formation/review contexts keep the candidate and append
    an auditable evidence marker. Draft rows are ignored by the registry resolver.
    """

    confirmed = tuple(
        sorted(
            (
                event
                for event in registry.events
                if event.confirmed and event.depth_domain == depth_domain
            ),
            key=lambda event: (
                event.top_depth,
                event.bottom_depth,
                event.event_type.value,
                event.event_id,
            ),
        )
    )
    kept: list[HydrocarbonCandidateInterval] = []
    suppressed_candidates: list[HydrocarbonCandidateInterval] = []
    for candidate in report.candidates:
        event = registry.resolve_for_interval(
            candidate.top_depth,
            candidate.bottom_depth,
            depth_domain=depth_domain,
        )
        if event is None:
            kept.append(candidate)
            continue
        impact = event.effective_impact
        if impact in {
            InterpretationImpact.EXCLUDE_GEOLOGICAL,
            InterpretationImpact.TECHNOLOGICAL_GAS,
        }:
            suppressed_candidates.append(_annotate_candidate(candidate, event))
            continue
        kept.append(_annotate_candidate(candidate, event))

    warnings = list(report.warnings)
    if suppressed_candidates:
        warnings.append(
            "Gas Context Registry suppressed "
            f"{len(suppressed_candidates)} automatic geological candidate(s); calculated curves, "
            "source gas values and the original automatic candidate evidence were preserved "
            "for audit."
        )
    opus_gasomer = report.opus_gasomer
    if opus_gasomer is not None:
        opus_gasomer = replace(
            opus_gasomer,
            intervals=tuple(
                interval
                for interval in opus_gasomer.intervals
                if not _suppresses_geological_candidate(
                    registry.resolve_for_interval(
                        interval.top_depth,
                        interval.bottom_depth,
                        depth_domain=depth_domain,
                    )
                )
            ),
        )
    return replace(
        report,
        candidates=tuple(kept),
        opus_gasomer=opus_gasomer,
        gas_context_events=confirmed,
        suppressed_candidates=tuple(suppressed_candidates),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _suppresses_geological_candidate(event: GasContextEvent | None) -> bool:
    return (
        event is not None
        and event.effective_impact
        in {
            InterpretationImpact.EXCLUDE_GEOLOGICAL,
            InterpretationImpact.TECHNOLOGICAL_GAS,
        }
    )


def _annotate_candidate(
    candidate: HydrocarbonCandidateInterval,
    event: GasContextEvent,
) -> HydrocarbonCandidateInterval:
    marker = (
        "gas-context: "
        f"event_id={event.event_id}; type={event.event_type.value}; "
        f"impact={event.effective_impact.value}; "
        f"interval={event.top_depth:g}-{event.bottom_depth:g}"
    )
    if event.comment.strip():
        marker += f"; comment={event.comment.strip()}"
    return replace(
        candidate,
        evidence=tuple((*candidate.evidence, marker)),
    )


__all__ = ["apply_gas_context_to_report"]
