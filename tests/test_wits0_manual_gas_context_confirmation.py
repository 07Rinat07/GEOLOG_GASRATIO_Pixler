from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.services.wits0_gas_context import Wits0GasOriginKind
from geoworkbench.services.wits0_manual_gas_context import (
    Wits0GasContextAxis,
    Wits0ManualGasContextInterval,
    resolve_manual_gas_context,
)


def _interval(*, confirmed: object) -> Wits0ManualGasContextInterval:
    return Wits0ManualGasContextInterval(
        interval_id="operator-gas-line-test",
        kind=Wits0GasOriginKind.GAS_LINE_TEST_GAS,
        axis=Wits0GasContextAxis.DEPTH,
        start=2500.0,
        end=2502.0,
        confirmed=confirmed,
    )


@pytest.mark.parametrize(
    "invalid",
    ["false", "true", "", 0, 1, None, [], {}, np.bool_(True), np.bool_(False)],
)
def test_manual_context_rejects_non_boolean_confirmation(invalid: object) -> None:
    # In particular, a truthy string must never turn an unconfirmed interval
    # into a source of operator-confirmed formation-exclusion evidence.
    with pytest.raises(ValueError, match="confirmed must be a boolean"):
        _interval(confirmed=invalid)


def test_only_explicit_true_manual_context_can_override_automatic_context() -> None:
    draft = _interval(confirmed=False)
    confirmed = _interval(confirmed=True)
    intervals = (draft,)

    assert draft.confirmed is False
    assert (
        resolve_manual_gas_context(
            intervals,
            axis=Wits0GasContextAxis.DEPTH,
            value=2501.0,
        )
        is None
    )
    assert (
        resolve_manual_gas_context(
            (confirmed,),
            axis=Wits0GasContextAxis.DEPTH,
            value=2501.0,
        )
        is confirmed
    )
    assert intervals == (draft,)
    assert draft.start == 2500.0 and draft.end == 2502.0
