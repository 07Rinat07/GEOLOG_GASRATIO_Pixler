from __future__ import annotations

import numpy as np
import pytest

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



def test_chromatograph_test_gas_has_priority_and_never_trains_background() -> None:
    classifier = _classifier()
    _prime_background(classifier)
    before = classifier.baseline_sample_count

    result = classifier.assess(
        Wits0GasContextObservation(
            total_gas=80.0,
            operation=Wits0GasOperation.CHROMATOGRAPH_TEST,
        )
    )

    assert result.kind is Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS
    assert "exclude_from_formation_interpretation" in result.reason_codes
    assert classifier.baseline_sample_count == before


def test_line_test_is_classified_even_without_total_gas_value() -> None:
    classifier = _classifier()

    result = classifier.assess(
        Wits0GasContextObservation(
            total_gas=None,
            operation=Wits0GasOperation.GAS_LINE_TEST,
        )
    )

    assert result.kind is Wits0GasOriginKind.GAS_LINE_TEST_GAS
    assert result.confidence == 1.0


@pytest.mark.parametrize(
    ("overrides", "error_field"),
    [
        ({"total_gas": "25.0"}, "total_gas"),
        ({"total_gas": True}, "total_gas"),
        ({"total_gas": np.bool_(False)}, "total_gas"),
        ({"total_gas": [25.0]}, "total_gas"),
        ({"total_gas": np.array(25.0)}, "total_gas"),
        ({"total_gas": 25.0 + 0j}, "total_gas"),
        ({"total_gas": float("nan")}, "total_gas"),
        ({"total_gas": float("inf")}, "total_gas"),
        ({"total_gas": -0.01}, "total_gas"),
        ({"total_gas": 10**999}, "total_gas"),
        ({"connection_lag_fraction": "1.0"}, "connection_lag_fraction"),
        ({"connection_lag_fraction": np.bool_(True)}, "connection_lag_fraction"),
        ({"connection_lag_fraction": float("nan")}, "connection_lag_fraction"),
        ({"connection_lag_fraction": -0.1}, "connection_lag_fraction"),
        ({"operation": "drilling"}, "operation"),
        ({"operation": None}, "operation"),
        ({"operation": Wits0GasOriginKind.BACKGROUND}, "operation"),
        ({"pumps_on": 0}, "pumps_on"),
        ({"pumps_on": np.bool_(True)}, "pumps_on"),
        ({"pumps_on": "false"}, "pumps_on"),
        ({"on_bottom": 1}, "on_bottom"),
        ({"on_bottom": np.bool_(False)}, "on_bottom"),
        ({"on_bottom": []}, "on_bottom"),
    ],
)
def test_observation_rejects_untyped_wits_inputs_before_baseline(
    overrides: dict[str, object], error_field: str
) -> None:
    classifier = _classifier()
    args: dict[str, object] = {
        "total_gas": 10.0,
        "operation": Wits0GasOperation.DRILLING,
        "pumps_on": True,
        "on_bottom": True,
    }
    args.update(overrides)
    with pytest.raises(ValueError, match=error_field):
        Wits0GasContextObservation(**args)
    assert classifier.baseline_sample_count == 0
    result = classifier.assess(
        Wits0GasContextObservation(
            total_gas=10.0,
            operation=Wits0GasOperation.DRILLING,
            pumps_on=True,
            on_bottom=True,
        )
    )
    assert result.kind is Wits0GasOriginKind.INSUFFICIENT_CONTEXT
    assert classifier.baseline_sample_count == 1


@pytest.mark.parametrize("gas", [0.0, 10.2, np.float32(12.5), np.int64(4)])
def test_observation_accepts_valid_typed_numeric_samples(gas: object) -> None:
    observation = Wits0GasContextObservation(
        total_gas=gas,
        operation=Wits0GasOperation.DRILLING,
        pumps_on=False,
        on_bottom=None,
        connection_lag_fraction=np.float64(1.0),
    )
    assert observation.total_gas is gas
    assert observation.connection_lag_fraction == 1.0
    assert observation.pumps_on is False


def test_observation_allows_missing_numeric_measurements() -> None:
    observation = Wits0GasContextObservation(
        total_gas=None,
        operation=Wits0GasOperation.UNKNOWN,
        pumps_on=None,
        on_bottom=None,
        connection_lag_fraction=None,
    )
    assert observation.total_gas is None
    assert observation.connection_lag_fraction is None
