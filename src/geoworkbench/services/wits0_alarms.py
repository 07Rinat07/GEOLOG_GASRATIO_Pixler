from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
import math
from numbers import Real


class AlarmSide(StrEnum):
    LOW = "low"
    HIGH = "high"


class AlarmTransition(StrEnum):
    NONE = "none"
    PENDING = "pending"
    ACTIVATED = "activated"
    ACKNOWLEDGED = "acknowledged"
    CLEARED = "cleared"


@dataclass(frozen=True, slots=True)
class AlarmLimits:
    """Validated alarm limits for one live parameter.

    Thresholds are expressed in the parameter's display unit.  Debounce is
    sample-count based so the evaluator remains independent from UI timers and
    transport cadence.  Hysteresis applies only while an alarm is active.
    """

    minimum: float | None = None
    maximum: float | None = None
    hysteresis: float = 0.0
    debounce_samples: int = 1

    def __post_init__(self) -> None:
        if self.minimum is None and self.maximum is None:
            raise ValueError("at least one alarm limit must be configured")
        for value, name in (
            (self.minimum, "minimum"),
            (self.maximum, "maximum"),
            (self.hysteresis, "hysteresis"),
        ):
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite real number")
        if self.minimum is not None and self.maximum is not None:
            if self.minimum >= self.maximum:
                raise ValueError("minimum must be lower than maximum")
        if self.hysteresis < 0:
            raise ValueError("hysteresis must be non-negative")
        if (
            isinstance(self.debounce_samples, bool)
            or not isinstance(self.debounce_samples, int)
            or self.debounce_samples < 1
        ):
            raise ValueError("debounce_samples must be a positive integer")


@dataclass(frozen=True, slots=True)
class AlarmState:
    active_side: AlarmSide | None = None
    pending_side: AlarmSide | None = None
    pending_count: int = 0
    acknowledged: bool = False


@dataclass(frozen=True, slots=True)
class AlarmEvaluation:
    state: AlarmState
    transition: AlarmTransition = AlarmTransition.NONE

    @property
    def is_active(self) -> bool:
        return self.state.active_side is not None

    @property
    def needs_attention(self) -> bool:
        return self.is_active and not self.state.acknowledged


def evaluate_alarm(
    limits: AlarmLimits,
    state: AlarmState,
    value: float | None,
) -> AlarmEvaluation:
    """Advance one alarm state with one live value.

    Missing/non-finite samples never fabricate a clear or activation.  They
    reset only an uncommitted debounce sequence and preserve an active alarm.
    """

    if (
        value is None
        or isinstance(value, bool)
        or not isinstance(value, Real)
        or not math.isfinite(value)
    ):
        if state.active_side is not None:
            return AlarmEvaluation(state)
        if state.pending_side is None:
            return AlarmEvaluation(state)
        return AlarmEvaluation(AlarmState())

    sample = float(value)
    if state.active_side is AlarmSide.LOW:
        assert limits.minimum is not None
        if sample < limits.minimum + limits.hysteresis:
            return AlarmEvaluation(state)
        cleared = AlarmState()
        next_evaluation = _evaluate_inactive(limits, cleared, sample)
        if next_evaluation.transition is AlarmTransition.NONE:
            return AlarmEvaluation(cleared, AlarmTransition.CLEARED)
        return next_evaluation

    if state.active_side is AlarmSide.HIGH:
        assert limits.maximum is not None
        if sample > limits.maximum - limits.hysteresis:
            return AlarmEvaluation(state)
        cleared = AlarmState()
        next_evaluation = _evaluate_inactive(limits, cleared, sample)
        if next_evaluation.transition is AlarmTransition.NONE:
            return AlarmEvaluation(cleared, AlarmTransition.CLEARED)
        return next_evaluation

    return _evaluate_inactive(limits, state, sample)


def acknowledge_alarm(state: AlarmState) -> AlarmEvaluation:
    """Acknowledge the currently active alarm without clearing it."""

    if state.active_side is None or state.acknowledged:
        return AlarmEvaluation(state)
    return AlarmEvaluation(
        replace(state, acknowledged=True),
        AlarmTransition.ACKNOWLEDGED,
    )


def _evaluate_inactive(
    limits: AlarmLimits,
    state: AlarmState,
    value: float,
) -> AlarmEvaluation:
    side = _violated_side(limits, value)
    if side is None:
        if state.pending_side is None:
            return AlarmEvaluation(AlarmState())
        return AlarmEvaluation(AlarmState(), AlarmTransition.CLEARED)

    count = state.pending_count + 1 if state.pending_side is side else 1
    if count >= limits.debounce_samples:
        return AlarmEvaluation(
            AlarmState(active_side=side),
            AlarmTransition.ACTIVATED,
        )
    return AlarmEvaluation(
        AlarmState(pending_side=side, pending_count=count),
        AlarmTransition.PENDING,
    )


def _violated_side(limits: AlarmLimits, value: float) -> AlarmSide | None:
    if limits.minimum is not None and value < limits.minimum:
        return AlarmSide.LOW
    if limits.maximum is not None and value > limits.maximum:
        return AlarmSide.HIGH
    return None


__all__ = [
    "AlarmEvaluation",
    "AlarmLimits",
    "AlarmSide",
    "AlarmState",
    "AlarmTransition",
    "acknowledge_alarm",
    "evaluate_alarm",
]
