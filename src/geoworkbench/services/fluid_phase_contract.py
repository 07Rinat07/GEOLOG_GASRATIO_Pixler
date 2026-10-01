from __future__ import annotations

from enum import StrEnum

from geoworkbench.services.localization import AppLanguage


class FluidPhaseContract(StrEnum):
    """Bounded user-facing fluid-phase vocabulary for interpretation outputs."""

    INDETERMINATE = "indeterminate"
    LIQUID = "liquid"
    LIGHT_OIL = "light_oil"
    LIQUID_OR_CONDENSATE = "liquid_or_condensate"
    GAS = "gas"


_LABELS: dict[FluidPhaseContract, dict[AppLanguage, str]] = {
    FluidPhaseContract.INDETERMINATE: {
        AppLanguage.RU: "УВ-флюид неопределённого типа",
        AppLanguage.KK: "түрі анықталмаған көмірсутекті флюид",
        AppLanguage.EN: "hydrocarbon fluid of undetermined type",
    },
    FluidPhaseContract.LIQUID: {
        AppLanguage.RU: "жидкая УВ-фаза",
        AppLanguage.KK: "сұйық КС фазасы",
        AppLanguage.EN: "liquid hydrocarbon phase",
    },
    FluidPhaseContract.LIGHT_OIL: {
        AppLanguage.RU: "признаки лёгкой нефтяной фазы",
        AppLanguage.KK: "жеңіл мұнай фазасының белгілері",
        AppLanguage.EN: "indications of a light-oil phase",
    },
    FluidPhaseContract.LIQUID_OR_CONDENSATE: {
        AppLanguage.RU: "жидкая УВ-фаза; возможны лёгкая нефть или газоконденсат",
        AppLanguage.KK: "сұйық КС фазасы; жеңіл мұнай немесе газ конденсаты болуы мүмкін",
        AppLanguage.EN: "liquid hydrocarbon phase; light oil or gas condensate possible",
    },
    FluidPhaseContract.GAS: {
        AppLanguage.RU: "газовая УВ-фаза",
        AppLanguage.KK: "газдық КС фазасы",
        AppLanguage.EN: "gaseous hydrocarbon phase",
    },
}


_EXACT_PHASE: dict[str, FluidPhaseContract] = {
    "probable_gas": FluidPhaseContract.GAS,
    "very_light_dry_gas": FluidPhaseContract.GAS,
    "light_dry_gas": FluidPhaseContract.GAS,
    "productive_gas_increasing_wetness": FluidPhaseContract.GAS,
    "gas_increasing_wetness": FluidPhaseContract.GAS,
    "wet_gas_or_gas_condensate": FluidPhaseContract.GAS,
    "gas_condensate_or_high_api_oil": FluidPhaseContract.LIQUID_OR_CONDENSATE,
    "light_oil_high_gor": FluidPhaseContract.LIGHT_OIL,
    "productive_oil_decreasing_gravity": FluidPhaseContract.LIQUID,
    "poor_low_gravity_oil": FluidPhaseContract.LIQUID,
    "heavy_or_residual_oil": FluidPhaseContract.LIQUID,
    "probable_liquid_hydrocarbons": FluidPhaseContract.LIQUID,
    "indeterminate": FluidPhaseContract.INDETERMINATE,
    "insufficient_data": FluidPhaseContract.INDETERMINATE,
    "opus_oxidized_residual_oil": FluidPhaseContract.LIQUID,
    "opus_oil": FluidPhaseContract.LIQUID,
    "opus_combustible_gas": FluidPhaseContract.GAS,
    "opus_water_dissolved_gas": FluidPhaseContract.INDETERMINATE,
    "opus_gas_condensate": FluidPhaseContract.LIQUID_OR_CONDENSATE,
    "opus_gassy_oil": FluidPhaseContract.LIQUID,
    "opus_gas_condensate_or_gassy_oil": FluidPhaseContract.LIQUID_OR_CONDENSATE,
    "opus_no_consensus": FluidPhaseContract.INDETERMINATE,
    "opus_gasomer_oxidized_residual_oil": FluidPhaseContract.LIQUID,
    "opus_gasomer_oil": FluidPhaseContract.LIQUID,
    "opus_gasomer_combustible_gas": FluidPhaseContract.GAS,
    "opus_gasomer_water_dissolved_gas": FluidPhaseContract.INDETERMINATE,
    "opus_gasomer_gas_condensate": FluidPhaseContract.LIQUID_OR_CONDENSATE,
    "opus_gasomer_gassy_oil": FluidPhaseContract.LIQUID,
    "opus_gasomer_undefined": FluidPhaseContract.INDETERMINATE,
    "opus_gasomer_no_consensus": FluidPhaseContract.INDETERMINATE,
}

_AMBIGUOUS_PREFIX = "opus_gasomer_ambiguous__"
_FALLBACK_PREFIX = "opus_fallback__"


def fluid_phase_label(
    phase: FluidPhaseContract,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    return _LABELS[phase][language]


def fluid_phase_from_hypothesis(fluid_hypothesis: str) -> FluidPhaseContract:
    """Map detailed calculation evidence to the bounded visible phase contract."""

    key = str(fluid_hypothesis or "").strip().casefold()
    if not key:
        return FluidPhaseContract.INDETERMINATE
    if key.startswith(_AMBIGUOUS_PREFIX):
        return FluidPhaseContract.INDETERMINATE
    if key.startswith(_FALLBACK_PREFIX):
        return fluid_phase_from_hypothesis(key[len(_FALLBACK_PREFIX) :])

    exact = _EXACT_PHASE.get(key)
    if exact is not None:
        return exact

    if any(token in key for token in ("indeterminate", "insufficient", "undefined", "no_consensus")):
        return FluidPhaseContract.INDETERMINATE
    if "water_dissolved_gas" in key:
        return FluidPhaseContract.INDETERMINATE
    if "gas_condensate_or_high_api_oil" in key or "gas_condensate_or_gassy_oil" in key:
        return FluidPhaseContract.LIQUID_OR_CONDENSATE
    if "gas_condensate" in key:
        return FluidPhaseContract.LIQUID_OR_CONDENSATE
    if "light_oil" in key:
        return FluidPhaseContract.LIGHT_OIL
    if "liquid_hydrocarbons" in key or "oil" in key:
        return FluidPhaseContract.LIQUID
    if any(token in key for token in ("probable_gas", "dry_gas", "combustible_gas", "gas_increasing")):
        return FluidPhaseContract.GAS
    return FluidPhaseContract.INDETERMINATE


def fluid_hypothesis_phase_label(
    fluid_hypothesis: str,
    language: AppLanguage = AppLanguage.RU,
) -> str:
    return fluid_phase_label(fluid_phase_from_hypothesis(fluid_hypothesis), language)


__all__ = [
    "FluidPhaseContract",
    "fluid_hypothesis_phase_label",
    "fluid_phase_from_hypothesis",
    "fluid_phase_label",
]
