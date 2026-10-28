from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.wits0_gas_context import (
    Wits0GasContextClassifierConfig,
    Wits0GasContextObservation,
    Wits0GasOperation,
    Wits0GasOriginKind,
)
from geoworkbench.services.wits0_gas_context_projection import (
    Wits0GasContextProjection,
)
from geoworkbench.services.wits0_manual_gas_context import (
    Wits0GasContextAxis,
    Wits0ManualGasContextInterval,
)


def _projection(
    *,
    manual_intervals: tuple[Wits0ManualGasContextInterval, ...] = (),
) -> Wits0GasContextProjection:
    return Wits0GasContextProjection(
        language=AppLanguage.EN,
        classifier_config=Wits0GasContextClassifierConfig(
            baseline_window=20,
            baseline_min_samples=5,
            minimum_absolute_rise=1.0,
            minimum_ratio_to_background=1.5,
            robust_sigma_multiplier=3.0,
        ),
        manual_intervals=manual_intervals,
    )


def _prime_background(projection: Wits0GasContextProjection) -> None:
    for index, total_gas in enumerate((10.0, 10.2, 9.9, 10.1, 10.0), start=1):
        result = projection.project(
            Wits0GasContextObservation(
                total_gas=total_gas,
                operation=Wits0GasOperation.DRILLING,
                pumps_on=True,
                on_bottom=True,
            ),
            axis=Wits0GasContextAxis.DEPTH,
            value=2500.0 + index,
        )
        assert result.resolved.kind in {
            Wits0GasOriginKind.INSUFFICIENT_CONTEXT,
            Wits0GasOriginKind.BACKGROUND,
        }


def test_projection_keeps_automatic_and_presentation_in_one_contract() -> None:
    projection = _projection()
    _prime_background(projection)

    result = projection.project(
        Wits0GasContextObservation(
            total_gas=25.0,
            operation=Wits0GasOperation.DRILLING,
            pumps_on=True,
            on_bottom=True,
        ),
        axis=Wits0GasContextAxis.DEPTH,
        value=2510.0,
    )

    assert result.automatic.kind is Wits0GasOriginKind.FORMATION_SHOW
    assert result.resolved.kind is Wits0GasOriginKind.FORMATION_SHOW
    assert result.presentation.effective_label == "Formation gas show"
    assert result.presentation.automatic_label == "Formation gas show"
    assert result.presentation.manual_interval_id is None


def test_projection_applies_confirmed_manual_qc_context_after_automatic_screening() -> None:
    projection = _projection(
        manual_intervals=(
            Wits0ManualGasContextInterval(
                interval_id="gc-calibration",
                kind=Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS,
                axis=Wits0GasContextAxis.DEPTH,
                start=2509.0,
                end=2511.0,
            ),
        )
    )
    _prime_background(projection)

    result = projection.project(
        Wits0GasContextObservation(
            total_gas=25.0,
            operation=Wits0GasOperation.DRILLING,
            pumps_on=True,
            on_bottom=True,
        ),
        axis=Wits0GasContextAxis.DEPTH,
        value=2510.0,
    )

    assert result.automatic.kind is Wits0GasOriginKind.FORMATION_SHOW
    assert result.resolved.kind is Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS
    assert result.presentation.effective_label == "Chromatograph test gas"
    assert result.presentation.automatic_label == "Formation gas show"
    assert result.presentation.manual_interval_id == "gc-calibration"
    assert result.presentation.excludes_formation_interpretation is True


def test_projection_can_refresh_manual_intervals_without_resetting_baseline() -> None:
    projection = _projection()
    _prime_background(projection)
    before = projection.baseline_sample_count
    projection.set_manual_intervals(
        (
            Wits0ManualGasContextInterval(
                interval_id="trip-1",
                kind=Wits0GasOriginKind.TRIP_GAS,
                axis=Wits0GasContextAxis.DEPTH,
                start=2509.0,
                end=2511.0,
            ),
        )
    )

    result = projection.project(
        Wits0GasContextObservation(
            total_gas=25.0,
            operation=Wits0GasOperation.DRILLING,
            pumps_on=True,
            on_bottom=True,
        ),
        axis=Wits0GasContextAxis.DEPTH,
        value=2510.0,
    )

    assert projection.baseline_sample_count == before
    assert result.resolved.kind is Wits0GasOriginKind.TRIP_GAS


def test_projection_reset_clears_only_automatic_baseline() -> None:
    interval = Wits0ManualGasContextInterval(
        interval_id="connection-1",
        kind=Wits0GasOriginKind.CONNECTION_GAS,
        axis=Wits0GasContextAxis.DEPTH,
        start=2509.0,
        end=2511.0,
    )
    projection = _projection(manual_intervals=(interval,))
    _prime_background(projection)

    projection.reset()

    assert projection.baseline_sample_count == 0
    assert projection.manual_intervals == (interval,)


@pytest.mark.parametrize(
    "axis,value",
    [
        ("depth", 2501.0),
        (None, 2501.0),
        (Wits0GasContextAxis.DEPTH, "2501"),
        (Wits0GasContextAxis.ELAPSED_TIME, np.bool_(True)),
        (Wits0GasContextAxis.DEPTH, float("nan")),
        (Wits0GasContextAxis.ELAPSED_TIME, -1.0),
    ],
)
@pytest.mark.parametrize("with_manual_interval", [False, True])
def test_invalid_projection_query_does_not_consume_automatic_baseline(
    axis: object, value: object, with_manual_interval: bool
) -> None:
    manual = Wits0ManualGasContextInterval(
        interval_id="calibration-1",
        kind=Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS,
        axis=Wits0GasContextAxis.DEPTH,
        start=2500.0,
        end=2502.0,
    )
    projection = _projection(manual_intervals=(manual,) if with_manual_interval else ())
    observation = Wits0GasContextObservation(
        total_gas=10.0,
        operation=Wits0GasOperation.DRILLING,
        pumps_on=True,
        on_bottom=True,
    )
    with pytest.raises(ValueError, match="axis must be|value must be"):
        projection.project(observation, axis=axis, value=value)
    assert projection.baseline_sample_count == 0

    valid = projection.project(
        observation, axis=Wits0GasContextAxis.DEPTH, value=2501.0
    )
    assert projection.baseline_sample_count == 1
    if with_manual_interval:
        assert valid.resolved.kind is Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS
        assert valid.resolved.manual_interval_id == "calibration-1"
    else:
        assert valid.resolved.kind is valid.automatic.kind
