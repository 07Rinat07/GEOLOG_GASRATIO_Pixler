from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from numbers import Real

import numpy as np

from geoworkbench.services.wits0_gas_context import (
    Wits0GasContextAssessment,
    Wits0GasOriginKind,
)


class Wits0GasContextResolutionSource(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"


class Wits0GasContextAxis(StrEnum):
    DEPTH = "depth"
    ELAPSED_TIME = "elapsed_time"


_MANUAL_PRIORITY: dict[Wits0GasOriginKind, int] = {
    Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS: 100,
    Wits0GasOriginKind.GAS_LINE_TEST_GAS: 95,
    Wits0GasOriginKind.LAG_TRACER_GAS: 90,
    Wits0GasOriginKind.CALIBRATION_GAS: 85,
    Wits0GasOriginKind.TRIP_GAS: 80,
    Wits0GasOriginKind.CONNECTION_GAS: 75,
    Wits0GasOriginKind.CIRCULATED_GAS: 70,
    Wits0GasOriginKind.RECYCLED_GAS: 65,
    Wits0GasOriginKind.FORMATION_SHOW: 50,
    Wits0GasOriginKind.BACKGROUND: 40,
    Wits0GasOriginKind.ELEVATED_UNCLASSIFIED: 20,
    Wits0GasOriginKind.INSUFFICIENT_CONTEXT: 0,
}



def _finite_real_coordinate(value: object, *, name: str, non_negative: bool) -> float:
    """Validate operator numeric input without accepting truthy text or booleans."""

    message = f"{name} must be a finite real scalar"
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (Real, np.integer, np.floating)
    ):
        raise ValueError(message)
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(message) from exc
    if not isfinite(numeric) or (non_negative and numeric < 0.0):
        raise ValueError(message + (" >= 0" if non_negative else ""))
    return numeric


def validate_gas_context_query(*, axis: Wits0GasContextAxis, value: float) -> float:
    """Validate a manual-context lookup before stateful gas screening."""

    if not isinstance(axis, Wits0GasContextAxis):
        raise ValueError("axis must be Wits0GasContextAxis")
    return _finite_real_coordinate(value, name="value", non_negative=True)


@dataclass(frozen=True, slots=True)
class Wits0ResolvedGasContext:
    """Effective gas context after deterministic manual-interval precedence."""

    kind: Wits0GasOriginKind
    source: Wits0GasContextResolutionSource
    automatic: Wits0GasContextAssessment
    manual_interval_id: str | None = None
    excludes_formation_interpretation: bool = False

    def __post_init__(self) -> None:
        if self.source is Wits0GasContextResolutionSource.MANUAL:
            if not self.manual_interval_id or not self.manual_interval_id.strip():
                raise ValueError("manual resolution requires manual_interval_id")
        elif self.manual_interval_id is not None:
            raise ValueError("automatic resolution cannot carry manual_interval_id")


@dataclass(frozen=True, slots=True)
class Wits0ManualGasContextInterval:
    """Operator-confirmed gas context used by live and report interpretation.

    start/end use the selected axis. For depth they are measured-depth coordinates;
    for elapsed-time they are seconds from acquisition/session start. event_value is
    optional and can store an observed TotalGas or test-gas reference value.
    """

    interval_id: str
    kind: Wits0GasOriginKind
    axis: Wits0GasContextAxis
    start: float
    end: float
    event_value: float | None = None
    event_unit: str | None = None
    comment: str = ""
    source: str = "manual"
    confirmed: bool = True

    def __post_init__(self) -> None:
        # Never promote a draft via truthiness (e.g. confirmed="false" or 1).
        if type(self.confirmed) is not bool:
            raise ValueError("confirmed must be a boolean")
        if not isinstance(self.interval_id, str) or not self.interval_id.strip():
            raise ValueError("interval_id must be non-empty text")
        if not isinstance(self.kind, Wits0GasOriginKind):
            raise ValueError("kind must be Wits0GasOriginKind")
        if not isinstance(self.axis, Wits0GasContextAxis):
            raise ValueError("axis must be Wits0GasContextAxis")
        start = _finite_real_coordinate(self.start, name="start", non_negative=True)
        end = _finite_real_coordinate(self.end, name="end", non_negative=True)
        if end < start:
            raise ValueError("end must be >= start")
        if self.event_value is not None:
            _finite_real_coordinate(
                self.event_value, name="event_value", non_negative=False
            )
        if self.event_unit is not None and (
            not isinstance(self.event_unit, str) or not self.event_unit.strip()
        ):
            raise ValueError("event_unit must be non-empty text or None")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be non-empty text")

    @property
    def excludes_formation_interpretation(self) -> bool:
        return self.kind in {
            Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS,
            Wits0GasOriginKind.GAS_LINE_TEST_GAS,
            Wits0GasOriginKind.LAG_TRACER_GAS,
            Wits0GasOriginKind.CALIBRATION_GAS,
            Wits0GasOriginKind.TRIP_GAS,
            Wits0GasOriginKind.CONNECTION_GAS,
            Wits0GasOriginKind.CIRCULATED_GAS,
            Wits0GasOriginKind.RECYCLED_GAS,
        }

    def contains(self, axis: Wits0GasContextAxis, value: float) -> bool:
        # A wrong-axis lookup still requires a valid numeric coordinate.
        numeric = validate_gas_context_query(axis=axis, value=value)
        if axis is not self.axis:
            return False
        return self.start <= numeric <= self.end


def resolve_manual_gas_context(
    intervals: tuple[Wits0ManualGasContextInterval, ...],
    *,
    axis: Wits0GasContextAxis,
    value: float,
) -> Wits0ManualGasContextInterval | None:
    """Return the highest-priority confirmed manual context at an axis position."""

    # A plain string such as "depth" is not a verified coordinate axis.
    # Reject it even for an empty interval list: silently falling back to
    # automatic formation gas may hide an operator-confirmed test event.
    # Validate even without intervals: invalid WITS query coordinates must never
    # silently fall back to automatic formation-gas classification.
    numeric = validate_gas_context_query(axis=axis, value=value)
    matches = tuple(
        interval
        for interval in intervals
        if interval.confirmed and interval.contains(axis, numeric)
    )
    if not matches:
        return None
    return max(
        matches,
        key=lambda item: (
            _MANUAL_PRIORITY.get(item.kind, 0),
            -(item.end - item.start),
            item.interval_id,
        ),
    )


def resolve_effective_gas_context(
    automatic: Wits0GasContextAssessment,
    intervals: tuple[Wits0ManualGasContextInterval, ...],
    *,
    axis: Wits0GasContextAxis,
    value: float,
) -> Wits0ResolvedGasContext:
    """Resolve automatic screening against confirmed operator context.

    A confirmed manual interval always wins at the requested axis coordinate.
    Draft/unconfirmed intervals remain invisible. When no confirmed interval
    matches, the automatic classifier result is preserved unchanged.
    """

    if not isinstance(automatic, Wits0GasContextAssessment):
        raise TypeError("automatic must use Wits0GasContextAssessment")
    manual = resolve_manual_gas_context(intervals, axis=axis, value=value)
    if manual is None:
        return Wits0ResolvedGasContext(
            kind=automatic.kind,
            source=Wits0GasContextResolutionSource.AUTOMATIC,
            automatic=automatic,
            excludes_formation_interpretation=(
                automatic.kind
                in {
                    Wits0GasOriginKind.CHROMATOGRAPH_TEST_GAS,
                    Wits0GasOriginKind.GAS_LINE_TEST_GAS,
                    Wits0GasOriginKind.LAG_TRACER_GAS,
                    Wits0GasOriginKind.CALIBRATION_GAS,
                    Wits0GasOriginKind.TRIP_GAS,
                    Wits0GasOriginKind.CONNECTION_GAS,
                    Wits0GasOriginKind.CIRCULATED_GAS,
                    Wits0GasOriginKind.RECYCLED_GAS,
                }
            ),
        )
    return Wits0ResolvedGasContext(
        kind=manual.kind,
        source=Wits0GasContextResolutionSource.MANUAL,
        automatic=automatic,
        manual_interval_id=manual.interval_id,
        excludes_formation_interpretation=manual.excludes_formation_interpretation,
    )


__all__ = [
    "Wits0GasContextAxis",
    "Wits0GasContextResolutionSource",
    "Wits0ResolvedGasContext",
    "Wits0ManualGasContextInterval",
    "validate_gas_context_query",
    "resolve_manual_gas_context",
    "resolve_effective_gas_context",
]
