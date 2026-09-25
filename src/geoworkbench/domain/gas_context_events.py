from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class GasContextEventType(StrEnum):
    BACKGROUND = "background"
    FORMATION_SHOW = "formation_show"
    CONNECTION_GAS = "connection_gas"
    TRIP_GAS = "trip_gas"
    SWAB_GAS = "swab_gas"
    CIRCULATED_GAS = "circulated_gas"
    RECYCLED_GAS = "recycled_gas"
    CHROMATOGRAPH_TEST_GAS = "chromatograph_test_gas"
    GAS_LINE_TEST_GAS = "gas_line_test_gas"
    LAG_TRACER_GAS = "lag_tracer_gas"
    CALIBRATION_GAS = "calibration_gas"
    ELEVATED_UNCLASSIFIED = "elevated_unclassified"
    OTHER_TECHNOLOGICAL = "other_technological"


class InterpretationImpact(StrEnum):
    EXCLUDE_GEOLOGICAL = "exclude_geological"
    TECHNOLOGICAL_GAS = "technological_gas"
    FORMATION_GAS = "formation_gas"
    REVIEW_REQUIRED = "review_required"


_EVENT_PRIORITY: dict[GasContextEventType, int] = {
    GasContextEventType.CHROMATOGRAPH_TEST_GAS: 120,
    GasContextEventType.GAS_LINE_TEST_GAS: 115,
    GasContextEventType.LAG_TRACER_GAS: 110,
    GasContextEventType.CALIBRATION_GAS: 105,
    GasContextEventType.SWAB_GAS: 95,
    GasContextEventType.TRIP_GAS: 90,
    GasContextEventType.CONNECTION_GAS: 85,
    GasContextEventType.CIRCULATED_GAS: 80,
    GasContextEventType.RECYCLED_GAS: 75,
    GasContextEventType.OTHER_TECHNOLOGICAL: 70,
    GasContextEventType.FORMATION_SHOW: 50,
    GasContextEventType.BACKGROUND: 40,
    GasContextEventType.ELEVATED_UNCLASSIFIED: 20,
}


_DEFAULT_IMPACT: dict[GasContextEventType, InterpretationImpact] = {
    GasContextEventType.CHROMATOGRAPH_TEST_GAS: InterpretationImpact.EXCLUDE_GEOLOGICAL,
    GasContextEventType.GAS_LINE_TEST_GAS: InterpretationImpact.EXCLUDE_GEOLOGICAL,
    GasContextEventType.LAG_TRACER_GAS: InterpretationImpact.EXCLUDE_GEOLOGICAL,
    GasContextEventType.CALIBRATION_GAS: InterpretationImpact.EXCLUDE_GEOLOGICAL,
    GasContextEventType.SWAB_GAS: InterpretationImpact.TECHNOLOGICAL_GAS,
    GasContextEventType.TRIP_GAS: InterpretationImpact.TECHNOLOGICAL_GAS,
    GasContextEventType.CONNECTION_GAS: InterpretationImpact.TECHNOLOGICAL_GAS,
    GasContextEventType.CIRCULATED_GAS: InterpretationImpact.TECHNOLOGICAL_GAS,
    GasContextEventType.RECYCLED_GAS: InterpretationImpact.TECHNOLOGICAL_GAS,
    GasContextEventType.OTHER_TECHNOLOGICAL: InterpretationImpact.TECHNOLOGICAL_GAS,
    GasContextEventType.FORMATION_SHOW: InterpretationImpact.FORMATION_GAS,
    GasContextEventType.BACKGROUND: InterpretationImpact.REVIEW_REQUIRED,
    GasContextEventType.ELEVATED_UNCLASSIFIED: InterpretationImpact.REVIEW_REQUIRED,
}


@dataclass(frozen=True, slots=True)
class GasContextEvent:
    """One operator/QC gas-context interval used by interpretation reports.

    Measured LAS/GS2/WITS curves are never modified by this object. reported_total_gas
    is an optional external/operator QC reference only.
    """

    event_id: str
    event_type: GasContextEventType
    top_depth: float
    bottom_depth: float
    impact: InterpretationImpact | None = None
    confirmed: bool = True
    reported_total_gas: float | None = None
    reported_unit: str | None = None
    comment: str = ""
    source: str = "manual"

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("event_id must be a non-empty string")
        if not isinstance(self.event_type, GasContextEventType):
            raise ValueError("event_type must be GasContextEventType")
        for value, name in (
            (self.top_depth, "top_depth"),
            (self.bottom_depth, "bottom_depth"),
        ):
            numeric = float(value)
            if not isfinite(numeric) or numeric < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.bottom_depth < self.top_depth:
            raise ValueError("bottom_depth must be >= top_depth")
        if self.impact is not None and not isinstance(self.impact, InterpretationImpact):
            raise ValueError("impact must be InterpretationImpact or None")
        if self.reported_total_gas is not None:
            value = float(self.reported_total_gas)
            if not isfinite(value) or value < 0.0:
                raise ValueError("reported_total_gas must be finite and non-negative")
        if self.reported_unit is not None and not self.reported_unit.strip():
            raise ValueError("reported_unit must be non-empty or None")
        if not isinstance(self.comment, str):
            raise ValueError("comment must be a string")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")

    @property
    def effective_impact(self) -> InterpretationImpact:
        return self.impact or _DEFAULT_IMPACT[self.event_type]

    def contains_depth(self, depth: float) -> bool:
        numeric = float(depth)
        return self.top_depth <= numeric <= self.bottom_depth


@dataclass(frozen=True, slots=True)
class GasContextRegistry:
    """Immutable view over repeated gas-context events for one well."""

    events: tuple[GasContextEvent, ...] = ()

    def __post_init__(self) -> None:
        ids = [event.event_id for event in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("gas context event IDs must be unique")

    def confirmed_at_depth(self, depth: float) -> tuple[GasContextEvent, ...]:
        return tuple(
            event
            for event in self.events
            if event.confirmed and event.contains_depth(depth)
        )

    def resolve_at_depth(self, depth: float) -> GasContextEvent | None:
        matches = self.confirmed_at_depth(depth)
        if not matches:
            return None
        return max(
            matches,
            key=lambda event: (
                _EVENT_PRIORITY[event.event_type],
                -(event.bottom_depth - event.top_depth),
                event.event_id,
            ),
        )

    def add(self, event: GasContextEvent) -> GasContextRegistry:
        if any(item.event_id == event.event_id for item in self.events):
            raise ValueError(f"gas context event already exists: {event.event_id}")
        return GasContextRegistry((*self.events, event))

    def replace(self, event: GasContextEvent) -> GasContextRegistry:
        if not any(item.event_id == event.event_id for item in self.events):
            raise KeyError(event.event_id)
        return GasContextRegistry(
            tuple(event if item.event_id == event.event_id else item for item in self.events)
        )

    def remove(self, event_id: str) -> GasContextRegistry:
        remaining = tuple(item for item in self.events if item.event_id != event_id)
        if len(remaining) == len(self.events):
            raise KeyError(event_id)
        return GasContextRegistry(remaining)


__all__ = [
    "GasContextEvent",
    "GasContextEventType",
    "GasContextRegistry",
    "InterpretationImpact",
]
