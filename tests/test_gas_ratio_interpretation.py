from geoworkbench.services.gas_ratio_interpretation import (
    classify_gas_ratio,
    classify_pixler_ratios,
    conservative_fluid_hypothesis,
)


def test_haworth_datalog_palette_uses_wh_bh_and_ch_together() -> None:
    assert (
        classify_gas_ratio(wetness=8.0, balance=30.0, character=0.3).code
        == "productive_gas_increasing_wetness"
    )
    assert (
        classify_gas_ratio(wetness=8.0, balance=5.0, character=0.3).code
        == "wet_gas_or_gas_condensate"
    )
    assert (
        classify_gas_ratio(wetness=8.0, balance=5.0, character=0.8).code
        == "light_oil_high_gor"
    )


def test_haworth_datalog_palette_covers_dry_oil_and_residual_ranges() -> None:
    assert (
        classify_gas_ratio(wetness=0.2, balance=50.0, character=0.2).code
        == "light_dry_gas"
    )
    assert (
        classify_gas_ratio(wetness=10.0, balance=120.0, character=0.2).code
        == "very_light_dry_gas"
    )
    assert (
        classify_gas_ratio(wetness=25.0, balance=20.0, character=0.8).code
        == "productive_oil_decreasing_gravity"
    )
    assert (
        classify_gas_ratio(wetness=25.0, balance=5.0, character=0.8).code
        == "poor_low_gravity_oil"
    )
    assert (
        classify_gas_ratio(wetness=45.0, balance=2.0, character=1.2).code
        == "heavy_or_residual_oil"
    )


def test_pixler_reports_overlapping_fluid_band_and_possible_water_shape() -> None:
    assessment = classify_pixler_ratios(
        c1_c2=12.0,
        c1_c3=20.0,
        c1_c4=15.0,
        c1_c5=30.0,
    )

    assert assessment.code == "light_oil_or_gas_condensate"
    assert assessment.profile_shape == "mixed"
    assert assessment.water_association_possible


def test_pixler_dry_gas_limit_does_not_claim_productivity() -> None:
    assessment = classify_pixler_ratios(
        c1_c2=70.0,
        c1_c3=90.0,
        c1_c4=120.0,
        c1_c5=180.0,
    )

    assert assessment.code == "very_light_methane_rich_gas"
    assert assessment.profile_shape == "positive"
    assert not assessment.water_association_possible



def test_conservative_fluid_gate_downgrades_weak_oil_like_signal() -> None:
    haworth = classify_gas_ratio(
        wetness=8.0,
        balance=5.0,
        character=0.8,
    )
    pixler = classify_pixler_ratios(
        c1_c2=9.0,
        c1_c3=15.0,
        c1_c4=20.0,
        c1_c5=25.0,
    )

    assert haworth.code == "light_oil_high_gor"
    assert pixler.code == "high_api_light_oil"
    assert pixler.profile_shape == "positive"
    assert (
        conservative_fluid_hypothesis(
            haworth,
            pixler=pixler,
            wetness_robust_z=1.7,
        )
        == "probable_liquid_hydrocarbons"
    )


def test_conservative_fluid_gate_keeps_specific_oil_only_with_strong_agreement() -> None:
    haworth = classify_gas_ratio(
        wetness=8.0,
        balance=5.0,
        character=0.8,
    )
    pixler = classify_pixler_ratios(
        c1_c2=9.0,
        c1_c3=15.0,
        c1_c4=20.0,
        c1_c5=25.0,
    )

    assert (
        conservative_fluid_hypothesis(
            haworth,
            pixler=pixler,
            wetness_robust_z=2.8,
        )
        == "light_oil_high_gor"
    )


def test_conservative_fluid_gate_keeps_transition_ambiguous() -> None:
    haworth = classify_gas_ratio(
        wetness=8.0,
        balance=5.0,
        character=0.8,
    )
    pixler = classify_pixler_ratios(
        c1_c2=12.0,
        c1_c3=18.0,
        c1_c4=24.0,
        c1_c5=32.0,
    )

    assert pixler.code == "light_oil_or_gas_condensate"
    assert (
        conservative_fluid_hypothesis(
            haworth,
            pixler=pixler,
            wetness_robust_z=3.0,
        )
        == "gas_condensate_or_high_api_oil"
    )


def test_conservative_fluid_gate_rejects_mixed_pixler_profile_for_specific_oil() -> None:
    haworth = classify_gas_ratio(
        wetness=25.0,
        balance=20.0,
        character=0.8,
    )
    pixler = classify_pixler_ratios(
        c1_c2=7.0,
        c1_c3=20.0,
        c1_c4=15.0,
        c1_c5=30.0,
    )

    assert pixler.code == "medium_api_oil"
    assert pixler.profile_shape == "mixed"
    assert (
        conservative_fluid_hypothesis(
            haworth,
            pixler=pixler,
            wetness_robust_z=3.5,
        )
        == "probable_liquid_hydrocarbons"
    )
