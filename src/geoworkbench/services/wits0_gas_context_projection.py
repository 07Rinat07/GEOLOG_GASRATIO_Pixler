from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_gas_context import (
    Wits0GasContextAssessment,
    Wits0GasContextClassifier,
    Wits0GasContextClassifierConfig,
    Wits0GasContextObservation,
)
from geoworkbench.services.wits0_gas_context_presentation import (
    Wits0GasContextPresentation,
    present_resolved_gas_context,
)
from geoworkbench.services.wits0_manual_gas_context import (
    Wits0GasContextAxis,
    Wits0ManualGasContextInterval,
    Wits0ResolvedGasContext,
    resolve_effective_gas_context,
)


@dataclass(frozen=True, slots=True)
class Wits0GasContextProjectionResult:
    """One end-to-end gas-context projection result for live/report adapters."""

    automatic: Wits0GasContextAssessment
    resolved: Wits0ResolvedGasContext
    presentation: Wits0GasContextPresentation


class Wits0GasContextProjection:
    """Shared stateful boundary from raw observation to presentation-ready context.

    The projection owns the robust automatic baseline classifier. Confirmed manual
    intervals are applied only after automatic assessment, preserving auditability.
    UI/report adapters therefore consume one contract without duplicating either
    classification or localization rules.
    """

    def __init__(
        self,
        *,
        language: AppLanguage = AppLanguage.RU,
        classifier_config: Wits0GasContextClassifierConfig | None = None,
        manual_intervals: tuple[Wits0ManualGasContextInterval, ...] = (),
    ) -> None:
        self.language = language
        self._classifier = Wits0GasContextClassifier(classifier_config)
        self._manual_intervals = tuple(manual_intervals)

    @property
    def baseline_sample_count(self) -> int:
        return self._classifier.baseline_sample_count

    @property
    def manual_intervals(self) -> tuple[Wits0ManualGasContextInterval, ...]:
        return self._manual_intervals

    def set_manual_intervals(
        self,
        intervals: tuple[Wits0ManualGasContextInterval, ...],
    ) -> None:
        self._manual_intervals = tuple(intervals)

    def reset(self) -> None:
        self._classifier.reset()

    def project(
        self,
        observation: Wits0GasContextObservation,
        *,
        axis: Wits0GasContextAxis,
        value: float,
    ) -> Wits0GasContextProjectionResult:
        automatic = self._classifier.assess(observation)
        resolved = resolve_effective_gas_context(
            automatic,
            self._manual_intervals,
            axis=axis,
            value=value,
        )
        return Wits0GasContextProjectionResult(
            automatic=automatic,
            resolved=resolved,
            presentation=present_resolved_gas_context(
                resolved,
                self.language,
            ),
        )


__all__ = [
    "Wits0GasContextProjection",
    "Wits0GasContextProjectionResult",
]
