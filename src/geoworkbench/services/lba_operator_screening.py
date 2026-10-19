"""Operator field observations for LBA signs: qualitative hypotheses only.

This does NOT replace Florovskaya's I–V classification or measure pore-fluid
saturation. Cases supplied by the operator are provisional, without calibrated
probabilities; absent gas, GIS and depth/blank controls prevent phase claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from geoworkbench.services.lba_standard import (
    assess_lba_standard,
    lba_color_code,
    lba_standard_type,
)


class LbaScreeningStatus(StrEnum):
    INVALID_OBSERVATION = "invalid_observation"
    INCOMPLETE_OBSERVATION = "incomplete_observation"
    UNCATALOGUED_PATTERN = "uncatalogued_pattern"
    OPERATOR_HYPOTHESIS = "operator_hypothesis"
    CONTAMINATION_REVIEW = "contamination_review"


class LbaFluidContext(StrEnum):
    GAS_ASSOCIATED = "gas_associated"
    GAS_CONDENSATE = "gas_condensate"
    LIGHT_OIL = "light_oil"
    OIL_OR_RESIDUAL_BITUMEN = "oil_or_residual_bitumen"


@dataclass(frozen=True, slots=True)
class LbaScreeningControls:
    """None means not checked, never a negative finding."""

    drilling_fluid_additives_present: bool | None = None
    coal_or_organic_matter_present: bool | None = None
    mud_or_solvent_blank_fluoresces: bool | None = None
    depth_and_lag_verified: bool | None = None


@dataclass(frozen=True, slots=True)
class LbaOperatorScreening:
    """Hypotheses for review, not probabilities or hydrocarbon-saturation output."""

    status: LbaScreeningStatus
    pattern_id: str | None
    candidate_contexts: tuple[LbaFluidContext, ...]
    warnings: tuple[str, ...]
    source: str = "operator-field-observations-2026-10-20-unvalidated"

    @property
    def confirms_reservoir_phase(self) -> bool:
        return False

    @property
    def confirms_hydrocarbon_saturation(self) -> bool:
        return False


# (residual-ring score, fluorescence colour, Florovskaya group).
# These are examples supplied by a field specialist, not universal thresholds.
_OPERATOR_PATTERNS: dict[
    tuple[int, str, int], tuple[LbaFluidContext, ...]
] = {
    (1, "БГ", 1): (LbaFluidContext.GAS_ASSOCIATED,),
    (2, "БГ", 1): (
        LbaFluidContext.GAS_ASSOCIATED,
        LbaFluidContext.GAS_CONDENSATE,
        LbaFluidContext.LIGHT_OIL,
    ),
    (2, "БЖ", 2): (LbaFluidContext.LIGHT_OIL, LbaFluidContext.GAS_CONDENSATE),
    (3, "БЖ", 2): (LbaFluidContext.LIGHT_OIL, LbaFluidContext.GAS_CONDENSATE),
    (3, "ГЖ", 2): (LbaFluidContext.LIGHT_OIL, LbaFluidContext.GAS_CONDENSATE),
    (3, "ОЖ", 3): (LbaFluidContext.OIL_OR_RESIDUAL_BITUMEN,),
}


def screen_lba_operator_pattern(
    *,
    group: int | None,
    type_id: str | None,
    colour: str | None,
    residual_ring_score: int | None,
    controls: LbaScreeningControls = LbaScreeningControls(),
) -> LbaOperatorScreening:
    """Match explicit operator examples; keep missing and contamination visible.

    Callers must separately validate the original sample, method, lag and
    mud blank, and correlate gas C1–C5 and suitable GIS. No phase can be
    determined from this result alone.
    """
    if not isinstance(controls, LbaScreeningControls):
        raise TypeError("controls must be LbaScreeningControls")
    if any(
        value is not None and not isinstance(value, bool)
        for value in (
            controls.drilling_fluid_additives_present,
            controls.coal_or_organic_matter_present,
            controls.mud_or_solvent_blank_fluoresces,
            controls.depth_and_lag_verified,
        )
    ):
        raise ValueError("QC control values must be true, false or unknown")

    if residual_ring_score is not None and (
        isinstance(residual_ring_score, bool)
        or not isinstance(residual_ring_score, int)
        or not 1 <= residual_ring_score <= 5
    ):
        return LbaOperatorScreening(
            LbaScreeningStatus.INVALID_OBSERVATION,
            None, (), ("invalid_residual_ring_score",),
        )

    if group is not None and (
        isinstance(group, bool) or not isinstance(group, int) or not 1 <= group <= 5
    ):
        return LbaOperatorScreening(
            LbaScreeningStatus.INVALID_OBSERVATION,
            None, (), ("invalid_florovskaya_group",),
        )
    if type_id is not None and type_id.strip() and lba_standard_type(type_id) is None:
        return LbaOperatorScreening(
            LbaScreeningStatus.INVALID_OBSERVATION,
            None, (), ("unknown_bitumoid_type",),
        )

    assessment = assess_lba_standard(
        group=group, type_id=type_id, color=colour,
        intensity=residual_ring_score,
    )
    if assessment is None:
        return LbaOperatorScreening(
            LbaScreeningStatus.INCOMPLETE_OBSERVATION,
            None, (), ("group_or_type_not_resolved",),
        )
    if assessment.conflicts:
        return LbaOperatorScreening(
            LbaScreeningStatus.INVALID_OBSERVATION,
            None, (), ("florovskaya_fields_conflict",),
        )
    if residual_ring_score is None or not colour or not lba_color_code(colour):
        return LbaOperatorScreening(
            LbaScreeningStatus.INCOMPLETE_OBSERVATION,
            None, (), ("ring_score_or_colour_missing",),
        )

    color_code = lba_color_code(colour)
    signature = (residual_ring_score, color_code, assessment.standard.group)
    candidates = _OPERATOR_PATTERNS.get(signature)
    if candidates is None:
        return LbaOperatorScreening(
            LbaScreeningStatus.UNCATALOGUED_PATTERN,
            f"{residual_ring_score}-{color_code}-{assessment.standard.code}",
            (), ("no_operator_rule_for_combination",),
        )

    warnings: list[str] = []
    if controls.depth_and_lag_verified is not True:
        warnings.append("sample_depth_or_lag_unverified")
    if controls.mud_or_solvent_blank_fluoresces is None:
        warnings.append("mud_solvent_blank_unknown")
    if controls.drilling_fluid_additives_present is None:
        warnings.append("drilling_additives_unknown")
    if controls.coal_or_organic_matter_present is None:
        warnings.append("coal_organic_matter_unknown")

    confounded = False
    for flag, code in (
        (controls.drilling_fluid_additives_present, "drilling_additives_present"),
        (controls.coal_or_organic_matter_present, "coal_organic_matter_present"),
        (controls.mud_or_solvent_blank_fluoresces, "mud_solvent_blank_fluorescent"),
    ):
        if flag is True:
            warnings.append(code)
            confounded = True

    return LbaOperatorScreening(
        (
            LbaScreeningStatus.CONTAMINATION_REVIEW
            if confounded else LbaScreeningStatus.OPERATOR_HYPOTHESIS
        ),
        f"{residual_ring_score}-{color_code}-{assessment.standard.code}",
        () if confounded else candidates,
        tuple(warnings),
    )


__all__ = [
    "LbaFluidContext",
    "LbaOperatorScreening",
    "LbaScreeningControls",
    "LbaScreeningStatus",
    "screen_lba_operator_pattern",
]
