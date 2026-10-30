"""WITS-INTERP-01: headless preliminary labels, not reservoir conclusions."""

from dataclasses import FrozenInstanceError

import pytest

from geoworkbench.services.fluid_phase_contract import FluidPhaseContract
from geoworkbench.services.gas_ratio_interpretation import (
    GasRatioAssessment,
    classify_gas_ratio,
    classify_pixler_ratios,
    conservative_fluid_hypothesis,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_fluid_screening import (
    project_wits0_fluid_screening,
)
from geoworkbench.services.wits0_gas_context import Wits0GasOriginKind


def _gas():
    return classify_gas_ratio(wetness=1.0, balance=3.0, character=0.2)


@pytest.mark.parametrize(
    ("origin", "expected_marker"),
    [
        (Wits0GasOriginKind.FORMATION_SHOW, True),
        (Wits0GasOriginKind.CONNECTION_GAS, False),
        (Wits0GasOriginKind.TRIP_GAS, False),
        (Wits0GasOriginKind.CIRCULATED_GAS, False),
        (Wits0GasOriginKind.BACKGROUND, False),
        (Wits0GasOriginKind.INSUFFICIENT_CONTEXT, False),
    ],
)
def test_fluid_label_never_reclassifies_operational_gas_as_formation(
    origin, expected_marker
) -> None:
    projected = project_wits0_fluid_screening(
        _gas(), pixler=None, wetness_robust_z=None, origin_kind=origin
    )
    assert projected.phase is FluidPhaseContract.GAS
    assert projected.palette_key == "gas"
    assert projected.formation_show_marker is expected_marker


@pytest.mark.parametrize(
    ("language", "prefix"),
    [
        (AppLanguage.RU, "Предварительный индикатор: "),
        (AppLanguage.KK, "Алдын ала индикатор: "),
        (AppLanguage.EN, "Preliminary indicator: "),
    ],
)
def test_screening_labels_are_explicitly_preliminary(language, prefix) -> None:
    projected = project_wits0_fluid_screening(
        _gas(),
        pixler=None,
        wetness_robust_z=None,
        origin_kind=Wits0GasOriginKind.CONNECTION_GAS,
    )
    assert projected.badge_text(language).startswith(prefix)
    assert projected.badge_text(language).strip() != prefix.strip()
    assert projected.formation_show_marker is False


def test_unconfirmed_oil_subtype_downgrades_to_generic_liquid() -> None:
    raw = classify_gas_ratio(wetness=20.0, balance=18.0, character=None)
    assert raw.code == "productive_oil_decreasing_gravity"
    projected = project_wits0_fluid_screening(
        raw,
        pixler=None,
        wetness_robust_z=None,
        origin_kind=Wits0GasOriginKind.FORMATION_SHOW,
    )
    assert projected.hypothesis_code == "probable_liquid_hydrocarbons"
    assert projected.phase is FluidPhaseContract.LIQUID
    assert projected.assessment_profile_ids == (raw.profile_id,)


def test_partial_pixler_does_not_promote_oil_specificity() -> None:
    raw = classify_gas_ratio(wetness=20.0, balance=18.0, character=None)
    incomplete = classify_pixler_ratios(
        c1_c2=7.0, c1_c3=12.0, c1_c4=None, c1_c5=None,
    )
    assert incomplete.profile_shape is None
    projected = project_wits0_fluid_screening(
        raw,
        pixler=incomplete,
        wetness_robust_z=3.0,
        origin_kind=Wits0GasOriginKind.CONNECTION_GAS,
    )
    assert projected.hypothesis_code == "probable_liquid_hydrocarbons"
    assert projected.formation_show_marker is False


def test_confirmed_compatible_evidence_reuses_existing_hypothesis() -> None:
    raw = classify_gas_ratio(wetness=20.0, balance=18.0, character=None)
    pixler = classify_pixler_ratios(
        c1_c2=6.0, c1_c3=12.0, c1_c4=20.0, c1_c5=25.0,
    )
    expected = conservative_fluid_hypothesis(
        raw, pixler=pixler, wetness_robust_z=3.0
    )
    assert expected == "productive_oil_decreasing_gravity"
    projected = project_wits0_fluid_screening(
        raw,
        pixler=pixler,
        wetness_robust_z=3.0,
        origin_kind=Wits0GasOriginKind.BACKGROUND,
    )
    assert projected.hypothesis_code == expected
    assert projected.phase is FluidPhaseContract.LIQUID
    assert projected.assessment_profile_ids == (raw.profile_id, pixler.profile_id)
    assert projected.formation_show_marker is False


def test_ambiguous_gas_condensate_light_oil_remains_ambiguous() -> None:
    raw = classify_gas_ratio(wetness=10.0, balance=5.0, character=0.5)
    projected = project_wits0_fluid_screening(
        raw,
        pixler=None,
        wetness_robust_z=None,
        origin_kind=Wits0GasOriginKind.FORMATION_SHOW,
    )
    assert projected.hypothesis_code == "gas_condensate_or_high_api_oil"
    assert projected.phase is FluidPhaseContract.LIQUID_OR_CONDENSATE
    assert projected.palette_key == projected.phase.value


def test_unknown_hypothesis_is_indeterminate_not_guessed() -> None:
    raw = GasRatioAssessment(
        code="unknown_vendor_class",
        wetness=1.0,
        balance=None,
        character=None,
        phase_code=None,
    )
    projected = project_wits0_fluid_screening(
        raw,
        pixler=None,
        wetness_robust_z=None,
        origin_kind=Wits0GasOriginKind.INSUFFICIENT_CONTEXT,
    )
    assert projected.phase is FluidPhaseContract.INDETERMINATE
    assert projected.formation_show_marker is False


@pytest.mark.parametrize(
    ("assessment", "pixler", "origin"),
    [
        ("gas", None, Wits0GasOriginKind.FORMATION_SHOW),
        (_gas(), "pixler", Wits0GasOriginKind.FORMATION_SHOW),
        (_gas(), None, "formation_show"),
    ],
)
def test_rejects_untyped_inputs(assessment, pixler, origin) -> None:
    with pytest.raises(TypeError):
        project_wits0_fluid_screening(
            assessment, pixler=pixler, wetness_robust_z=None, origin_kind=origin
        )


def test_projection_is_immutable_and_rejects_unknown_language() -> None:
    raw = _gas()
    projected = project_wits0_fluid_screening(
        raw,
        pixler=None,
        wetness_robust_z=None,
        origin_kind=Wits0GasOriginKind.FORMATION_SHOW,
    )
    with pytest.raises(FrozenInstanceError):
        projected.phase = FluidPhaseContract.LIQUID
    with pytest.raises(TypeError):
        projected.badge_text("ru")
    assert raw == _gas()
