import math

import pytest

from geoworkbench.services.wits0_alarms import (
    AlarmLimits,
    AlarmSide,
    AlarmState,
    AlarmTransition,
    acknowledge_alarm,
    evaluate_alarm,
)


def test_alarm_limits_validate_threshold_contract() -> None:
    with pytest.raises(ValueError, match="at least one"):
        AlarmLimits()
    with pytest.raises(ValueError, match="lower"):
        AlarmLimits(minimum=10.0, maximum=10.0)
    with pytest.raises(ValueError, match="finite"):
        AlarmLimits(maximum=math.inf)
    with pytest.raises(ValueError, match="non-negative"):
        AlarmLimits(maximum=10.0, hysteresis=-0.1)
    with pytest.raises(ValueError, match="positive integer"):
        AlarmLimits(maximum=10.0, debounce_samples=0)


def test_high_alarm_requires_consecutive_debounce_samples() -> None:
    limits = AlarmLimits(maximum=100.0, debounce_samples=3)
    state = AlarmState()

    first = evaluate_alarm(limits, state, 101.0)
    second = evaluate_alarm(limits, first.state, 105.0)
    third = evaluate_alarm(limits, second.state, 102.0)

    assert first.transition is AlarmTransition.PENDING
    assert first.state.pending_count == 1
    assert second.state.pending_count == 2
    assert third.transition is AlarmTransition.ACTIVATED
    assert third.state.active_side is AlarmSide.HIGH
    assert third.needs_attention


def test_debounce_resets_when_value_returns_inside_limits() -> None:
    limits = AlarmLimits(maximum=100.0, debounce_samples=2)
    pending = evaluate_alarm(limits, AlarmState(), 101.0)

    cleared = evaluate_alarm(limits, pending.state, 99.0)

    assert cleared.transition is AlarmTransition.CLEARED
    assert cleared.state == AlarmState()


def test_high_alarm_uses_hysteresis_before_clearing() -> None:
    limits = AlarmLimits(maximum=100.0, hysteresis=5.0)
    active = evaluate_alarm(limits, AlarmState(), 101.0)
    assert active.state.active_side is AlarmSide.HIGH

    still_active = evaluate_alarm(limits, active.state, 97.0)
    cleared = evaluate_alarm(limits, still_active.state, 95.0)

    assert still_active.state.active_side is AlarmSide.HIGH
    assert cleared.transition is AlarmTransition.CLEARED
    assert cleared.state == AlarmState()


def test_low_alarm_uses_hysteresis_before_clearing() -> None:
    limits = AlarmLimits(minimum=20.0, hysteresis=2.0)
    active = evaluate_alarm(limits, AlarmState(), 19.0)

    still_active = evaluate_alarm(limits, active.state, 21.5)
    cleared = evaluate_alarm(limits, still_active.state, 22.0)

    assert still_active.state.active_side is AlarmSide.LOW
    assert cleared.transition is AlarmTransition.CLEARED


def test_acknowledgement_silences_attention_but_does_not_clear_alarm() -> None:
    limits = AlarmLimits(maximum=100.0)
    active = evaluate_alarm(limits, AlarmState(), 110.0)

    acknowledged = acknowledge_alarm(active.state)

    assert acknowledged.transition is AlarmTransition.ACKNOWLEDGED
    assert acknowledged.state.active_side is AlarmSide.HIGH
    assert acknowledged.state.acknowledged
    assert not acknowledged.needs_attention

    persisted = evaluate_alarm(limits, acknowledged.state, 108.0)
    assert persisted.state.acknowledged
    assert persisted.state.active_side is AlarmSide.HIGH


def test_clear_resets_acknowledgement_for_next_alarm() -> None:
    limits = AlarmLimits(maximum=100.0)
    active = evaluate_alarm(limits, AlarmState(), 110.0)
    acknowledged = acknowledge_alarm(active.state)
    cleared = evaluate_alarm(limits, acknowledged.state, 90.0)
    reactivated = evaluate_alarm(limits, cleared.state, 120.0)

    assert cleared.state == AlarmState()
    assert reactivated.state.active_side is AlarmSide.HIGH
    assert not reactivated.state.acknowledged
    assert reactivated.needs_attention


def test_non_finite_sample_does_not_clear_active_alarm() -> None:
    limits = AlarmLimits(maximum=100.0, debounce_samples=2)
    pending = evaluate_alarm(limits, AlarmState(), 110.0)
    reset_pending = evaluate_alarm(limits, pending.state, math.nan)

    active = evaluate_alarm(limits, AlarmState(), 110.0)
    active = evaluate_alarm(limits, active.state, 111.0)
    preserved = evaluate_alarm(limits, active.state, None)

    assert reset_pending.state == AlarmState()
    assert preserved.state.active_side is AlarmSide.HIGH


def test_opposite_limit_can_start_after_active_alarm_clears() -> None:
    limits = AlarmLimits(minimum=20.0, maximum=100.0, debounce_samples=2)
    high_pending = evaluate_alarm(limits, AlarmState(), 110.0)
    high_active = evaluate_alarm(limits, high_pending.state, 111.0)

    low_pending = evaluate_alarm(limits, high_active.state, 10.0)
    low_active = evaluate_alarm(limits, low_pending.state, 9.0)

    assert low_pending.transition is AlarmTransition.PENDING
    assert low_pending.state.pending_side is AlarmSide.LOW
    assert low_active.transition is AlarmTransition.ACTIVATED
    assert low_active.state.active_side is AlarmSide.LOW
