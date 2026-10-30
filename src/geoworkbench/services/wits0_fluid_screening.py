"""Conservative, presentation-only WITS fluid screening projection.

The existing versioned Haworth/Pixler classifiers own the calculations. This
module never derives a reservoir claim from a WITS observation or gas origin.
"""

from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.services.fluid_phase_contract import (
    FluidPhaseContract,
    fluid_phase_from_hypothesis,
    fluid_phase_label,
)
from geoworkbench.services.gas_ratio_interpretation import (
    GasRatioAssessment,
    PixlerAssessment,
    conservative_fluid_hypothesis,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_gas_context import Wits0GasOriginKind


_PRELIMINARY_PREFIX = {
    AppLanguage.RU: "Предварительный индикатор: ",
    AppLanguage.KK: "Алдын ала индикатор: ",
    AppLanguage.EN: "Preliminary indicator: ",
}


@dataclass(frozen=True, slots=True)
class Wits0FluidScreeningProjection:
    """One provisional fluid label; operational gas origin remains independent."""

    hypothesis_code: str
    phase: FluidPhaseContract
    origin_kind: Wits0GasOriginKind
    assessment_profile_ids: tuple[str, ...]

    @property
    def palette_key(self) -> str:
        """Single semantic key for a future badge and its plot stripe."""

        return self.phase.value

    @property
    def formation_show_marker(self) -> bool:
        """Only the independent gas-origin classifier may mark a formation show."""

        return self.origin_kind is Wits0GasOriginKind.FORMATION_SHOW

    def badge_text(self, language: AppLanguage) -> str:
        if not isinstance(language, AppLanguage):
            raise TypeError("language must use AppLanguage")
        return _PRELIMINARY_PREFIX[language] + fluid_phase_label(self.phase, language)


def project_wits0_fluid_screening(
    assessment: GasRatioAssessment,
    *,
    pixler: PixlerAssessment | None,
    wetness_robust_z: float | None,
    origin_kind: Wits0GasOriginKind,
) -> Wits0FluidScreeningProjection:
    """Project existing conservative evidence, without new fluid thresholds.

    The caller must supply assessments from the existing versioned calculation
    pipeline and the separately assessed operational origin. An unconfirmed oil
    subtype is downgraded by conservative_fluid_hypothesis; an operational gas
    transient is never promoted to a formation-show marker by its composition.
    This does not authorize an automatic reservoir/productivity conclusion.
    """

    if not isinstance(assessment, GasRatioAssessment):
        raise TypeError("assessment must use GasRatioAssessment")
    if pixler is not None and not isinstance(pixler, PixlerAssessment):
        raise TypeError("pixler must use PixlerAssessment or None")
    if not isinstance(origin_kind, Wits0GasOriginKind):
        raise TypeError("origin_kind must use Wits0GasOriginKind")

    hypothesis = conservative_fluid_hypothesis(
        assessment,
        pixler=pixler,
        wetness_robust_z=wetness_robust_z,
    )
    profile_ids = (
        (assessment.profile_id,)
        if pixler is None
        else (assessment.profile_id, pixler.profile_id)
    )
    return Wits0FluidScreeningProjection(
        hypothesis_code=hypothesis,
        phase=fluid_phase_from_hypothesis(hypothesis),
        origin_kind=origin_kind,
        assessment_profile_ids=profile_ids,
    )


__all__ = ["Wits0FluidScreeningProjection", "project_wits0_fluid_screening"]
