from __future__ import annotations

import pytest

from geoworkbench.services.fluid_phase_contract import (
    FluidPhaseContract,
    fluid_hypothesis_phase_label,
    fluid_phase_from_hypothesis,
)
from geoworkbench.services.localization import AppLanguage


@pytest.mark.parametrize(
    ("hypothesis", "phase"),
    [
        ("probable_gas", FluidPhaseContract.GAS),
        ("wet_gas_or_gas_condensate", FluidPhaseContract.GAS),
        ("light_oil_high_gor", FluidPhaseContract.LIGHT_OIL),
        ("productive_oil_decreasing_gravity", FluidPhaseContract.LIQUID),
        ("heavy_or_residual_oil", FluidPhaseContract.LIQUID),
        ("probable_liquid_hydrocarbons", FluidPhaseContract.LIQUID),
        ("gas_condensate_or_high_api_oil", FluidPhaseContract.LIQUID_OR_CONDENSATE),
        ("opus_gasomer_oil", FluidPhaseContract.LIQUID),
        ("opus_gasomer_combustible_gas", FluidPhaseContract.GAS),
        ("opus_gasomer_gas_condensate", FluidPhaseContract.LIQUID_OR_CONDENSATE),
        ("opus_gasomer_water_dissolved_gas", FluidPhaseContract.INDETERMINATE),
        ("opus_gasomer_undefined", FluidPhaseContract.INDETERMINATE),
        ("opus_gasomer_ambiguous__possible__2-3", FluidPhaseContract.INDETERMINATE),
        ("unknown_future_code", FluidPhaseContract.INDETERMINATE),
        ("unknown_oil_classification", FluidPhaseContract.INDETERMINATE),
        ("plugin_gas_classification", FluidPhaseContract.INDETERMINATE),
        ("probable_gas_typo", FluidPhaseContract.INDETERMINATE),
        ("opus_fallback__unknown_light_oil", FluidPhaseContract.INDETERMINATE),
    ],
)
def test_fluid_hypotheses_map_to_bounded_phase_contract(
    hypothesis: str,
    phase: FluidPhaseContract,
) -> None:
    assert fluid_phase_from_hypothesis(hypothesis) is phase


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (AppLanguage.RU, "жидкая УВ-фаза; возможны лёгкая нефть или газоконденсат"),
        (
            AppLanguage.KK,
            "сұйық КС фазасы; жеңіл мұнай немесе газ конденсаты болуы мүмкін",
        ),
        (
            AppLanguage.EN,
            "liquid hydrocarbon phase; light oil or gas condensate possible",
        ),
    ],
)
def test_fluid_phase_labels_are_semantically_equivalent_across_languages(
    language: AppLanguage,
    expected: str,
) -> None:
    assert (
        fluid_hypothesis_phase_label("opus_gasomer_gas_condensate", language)
        == expected
    )


def test_opus_fallback_uses_underlying_hypothesis_phase() -> None:
    assert (
        fluid_phase_from_hypothesis("opus_fallback__light_oil_high_gor")
        is FluidPhaseContract.LIGHT_OIL
    )


def test_nested_fallback_is_bounded_without_recursive_stack_growth() -> None:
    assert (
        fluid_phase_from_hypothesis("opus_fallback__" * 2000 + "probable_gas")
        is FluidPhaseContract.GAS
    )
    assert (
        fluid_phase_from_hypothesis("opus_fallback__" * 2000 + "plugin_gas")
        is FluidPhaseContract.INDETERMINATE
    )
