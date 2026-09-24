from __future__ import annotations

from geoworkbench.services.wits0_gas_context import Wits0GasOriginKind
from geoworkbench.services.wits0_manual_gas_context import (
    Wits0GasContextAxis,
    Wits0ManualGasContextInterval,
    resolve_manual_gas_context,
)


def test_manual_test_interval_overrides_overlapping_formation_show() -> None:
    intervals = (
        Wits0ManualGasContextInterval(
            interval_id="formation",
            kind=Wits0GasOriginKind.FORMATION_SHOW,
            axis=Wits0GasContextAxis.DEPTH,
            start=2500.0,
            end=2510.0,
        ),
        Wits0ManualGasContextInterval(
            interval_id="gc-test",
            kind=Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS,
            axis=Wits0GasContextAxis.DEPTH,
            start=2504.0,
            end=2505.0,
            event_value=1.0,
            event_unit="%",
            comment="Certified C1-C5 calibration mix",
        ),
    )

    resolved = resolve_manual_gas_context(
        intervals,
        axis=Wits0GasContextAxis.DEPTH,
        value=2504.5,
    )

    assert resolved is not None
    assert resolved.kind is Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS
    assert resolved.excludes_formation_interpretation is True


def test_unconfirmed_manual_interval_is_ignored() -> None:
    interval = Wits0ManualGasContextInterval(
        interval_id="draft-trip",
        kind=Wits0GasOriginKind.TRIP_GAS,
        axis=Wits0GasContextAxis.ELAPSED_TIME,
        start=100.0,
        end=200.0,
        confirmed=False,
    )

    assert (
        resolve_manual_gas_context(
            (interval,),
            axis=Wits0GasContextAxis.ELAPSED_TIME,
            value=150.0,
        )
        is None
    )
