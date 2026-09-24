from __future__ import annotations

from geoworkbench.services.wits0_gas_context import (
    Wits0GasContextClassifier,
    Wits0GasContextClassifierConfig,
    Wits0GasContextObservation,
    Wits0GasOperation,
    Wits0GasOriginKind,
)


def _classifier() -> Wits0GasContextClassifier:
    return Wits0GasContextClassifier(
        Wits0GasContextClassifierConfig(
            baseline_window=20,
            baseline_min_samples=5,
            minimum_absolute_rise=1.0,
            minimum_ratio_to_background=1.5,
            robust_sigma_multiplier=3.0,
        )
    )


def _prime_background(classifier: Wits0GasContextClassifier) -> None:
    for value in (10.0, 10.2, 9.9, 10.1, 10.0):
        result = classifier.assess(
            Wits0GasContextObservation(
                total_gas=value,
                operation=Wits0GasOperation.DRILLING,
                pumps_on=True,
                on_bottom=True,
            )
        )
        assert result.kind in {
            Wits0GasOriginKind.INSUFFICIENT_CONTEXT,
            Wits0GasOriginKind.BACKGROUND,
        }


def test_stable_drilling_excursion_is_formation_show() -> None:
    classifier = _classifier()
    _prime_background(classifier)

    result = classifier.assess(
        Wits0GasContextObservation(
            total_gas=25.0,
            operation=Wits0GasOperation.DRILLING,
            pumps_on=True,
            on_bottom=True,
        )
    )

    assert result.kind is Wits0GasOriginKind.FORMATION_SHOW
    assert result.background is not None
    assert result.ratio_to_background is not None
    assert result.ratio_to_background > 2.0


def test_connection_context_takes_precedence_over_formation_show() -> None:
    classifier = _classifier()
    _prime_background(classifier)

    result = classifier.assess(
        Wits0GasContextObservation(
            total_gas=25.0,
            operation=Wits0GasOperation.CONNECTION,
            pumps_on=True,
            on_bottom=True,
            connection_lag_fraction=1.0,
        )
    )

    assert result.kind is Wits0GasOriginKind.CONNECTION_GAS
    assert "arrival_near_lag" in result.reason_codes


def test_trip_context_takes_precedence_over_formation_show() -> None:
    classifier = _classifier()
    _prime_background(classifier)

    result = classifier.assess(
        Wits0GasContextObservation(
            total_gas=30.0,
            operation=Wits0GasOperation.TRIP,
            pumps_on=True,
            on_bottom=False,
        )
    )

    assert result.kind is Wits0GasOriginKind.TRIP_GAS


def test_background_does_not_learn_elevated_transient() -> None:
    classifier = _classifier()
    _prime_background(classifier)
    before = classifier.baseline_sample_count

    result = classifier.assess(
        Wits0GasContextObservation(
            total_gas=50.0,
            operation=Wits0GasOperation.CONNECTION,
            connection_lag_fraction=1.0,
        )
    )

    assert result.kind is Wits0GasOriginKind.CONNECTION_GAS
    assert classifier.baseline_sample_count == before


def test_connection_peak_outside_lag_window_is_not_forced_to_connection_gas() -> None:
    classifier = _classifier()
    _prime_background(classifier)

    result = classifier.assess(
        Wits0GasContextObservation(
            total_gas=25.0,
            operation=Wits0GasOperation.CONNECTION,
            connection_lag_fraction=2.0,
        )
    )

    assert result.kind is Wits0GasOriginKind.ELEVATED_UNCLASSIFIED
