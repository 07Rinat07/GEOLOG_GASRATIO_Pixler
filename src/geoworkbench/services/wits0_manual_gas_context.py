from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

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
        if not self.interval_id.strip():
            raise ValueError("interval_id must not be empty")
        if not isinstance(self.kind, Wits0GasOriginKind):
            raise ValueError("kind must be Wits0GasOriginKind")
        if not isinstance(self.axis, Wits0GasContextAxis):
            raise ValueError("axis must be Wits0GasContextAxis")
        for value, name in ((self.start, "start"), (self.end, "end")):
            numeric = float(value)
            if not isfinite(numeric) or numeric < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.end < self.start:
            raise ValueError("end must be >= start")
        if self.event_value is not None and not isfinite(float(self.event_value)):
            raise ValueError("event_value must be finite or None")
        if self.event_unit is not None and not self.event_unit.strip():
            raise ValueError("event_unit must be non-empty or None")
        if not self.source.strip():
            raise ValueError("source must not be empty")

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
        if axis is not self.axis:
            return False
        numeric = float(value)
        return self.start <= numeric <= self.end


def resolve_manual_gas_context(
    intervals: tuple[Wits0ManualGasContextInterval, ...],
    *,
    axis: Wits0GasContextAxis,
    value: float,
) -> Wits0ManualGasContextInterval | None:
    """Return the highest-priority confirmed manual context at an axis position."""

    matches = tuple(
        interval
        for interval in intervals
        if interval.confirmed and interval.contains(axis, value)
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
    "resolve_manual_gas_context",
    "resolve_effective_gas_context",
]
