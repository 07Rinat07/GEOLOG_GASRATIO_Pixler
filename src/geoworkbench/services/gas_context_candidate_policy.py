from __future__ import annotations

from dataclasses import replace

from geoworkbench.domain.gas_context_events import (
    GasContextEvent,
    GasContextRegistry,
    InterpretationImpact,
)
from geoworkbench.services.hydrocarbon_interpretation_legacy import (
    HydrocarbonCandidateInterval,
    HydrocarbonInterpretationReport,
)


def apply_gas_context_to_report(
    report: HydrocarbonInterpretationReport,
    registry: GasContextRegistry,
) -> HydrocarbonInterpretationReport:
    """Apply confirmed operator gas context to automatic interval classification.

    Calculated source curves and candidate metrics are never mutated. Contexts marked
    as technological/excluded suppress an automatic geological candidate from the
    prospective-interval list; formation/review contexts keep the candidate and append
    an auditable evidence marker. Draft rows are ignored by the registry resolver.
    """

    confirmed = tuple(
        sorted(
            (event for event in registry.events if event.confirmed),
            key=lambda event: (
                event.top_depth,
                event.bottom_depth,
                event.event_type.value,
                event.event_id,
            ),
        )
    )
    kept: list[HydrocarbonCandidateInterval] = []
    suppressed = 0
    for candidate in report.candidates:
        event = registry.resolve_for_interval(
            candidate.top_depth,
            candidate.bottom_depth,
        )
        if event is None:
            kept.append(candidate)
            continue
        impact = event.effective_impact
        if impact in {
            InterpretationImpact.EXCLUDE_GEOLOGICAL,
            InterpretationImpact.TECHNOLOGICAL_GAS,
        }:
            suppressed += 1
            continue
        kept.append(_annotate_candidate(candidate, event))

    warnings = list(report.warnings)
    if suppressed:
        warnings.append(
            "Gas Context Registry suppressed "
            f"{suppressed} automatic geological candidate(s); calculated curves and "
            "source gas values were preserved unchanged."
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
                    )
                )
            ),
        )
    return replace(
        report,
        candidates=tuple(kept),
        opus_gasomer=opus_gasomer,
        gas_context_events=confirmed,
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
