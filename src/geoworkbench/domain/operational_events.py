from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import TypeAlias


class OperationalEventKind(StrEnum):
    DRILLING = "drilling"
    GAS = "gas"
    SHOW = "show"
    SAMPLE = "sample"
    CASING = "casing"
    FORMATION_TOP = "formation_top"


class OperationalEventQcFlag(StrEnum):
    DUPLICATE = "duplicate"
    OUT_OF_ORDER = "out_of_order"
    GAP = "gap"
    STALE = "stale"
    CALIBRATION_MISSING = "calibration_missing"
    CALIBRATION_EXPIRED = "calibration_expired"


@dataclass(frozen=True, slots=True)
class DrillingEventPayload:
    activity: str | None = None
    rop_m_per_h: float | None = None
    rpm: float | None = None
    wob_kn: float | None = None
    hookload_kn: float | None = None

    def __post_init__(self) -> None:
        _validate_optional_text(self.activity, "activity")
        _validate_optional_non_negative(self.rop_m_per_h, "rop_m_per_h")
        _validate_optional_non_negative(self.rpm, "rpm")
        _validate_optional_non_negative(self.wob_kn, "wob_kn")
        _validate_optional_non_negative(self.hookload_kn, "hookload_kn")
        if all(
            value is None
            for value in (
                self.activity,
                self.rop_m_per_h,
                self.rpm,
                self.wob_kn,
                self.hookload_kn,
            )
        ):
            raise ValueError("Drilling event payload не должен быть пустым")


@dataclass(frozen=True, slots=True)
class GasEventPayload:
    total_gas_percent: float | None = None
    methane_percent: float | None = None
    ethane_percent: float | None = None
    propane_percent: float | None = None
    connection_gas_percent: float | None = None

    def __post_init__(self) -> None:
        values = (
            (self.total_gas_percent, "total_gas_percent"),
            (self.methane_percent, "methane_percent"),
            (self.ethane_percent, "ethane_percent"),
            (self.propane_percent, "propane_percent"),
            (self.connection_gas_percent, "connection_gas_percent"),
        )
        for value, name in values:
            _validate_optional_range(value, name, 0.0, 100.0)
        if all(value is None for value, _ in values):
            raise ValueError("Gas event payload не должен быть пустым")


@dataclass(frozen=True, slots=True)
class ShowEventPayload:
    show_type: str
    intensity: int | None = None
    fluorescence_color: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text(self.show_type, "show_type")
        _validate_optional_text(self.fluorescence_color, "fluorescence_color")
        _validate_optional_text(self.description, "description")
        if self.intensity is not None:
            if isinstance(self.intensity, bool) or not isinstance(self.intensity, int):
                raise ValueError("intensity должен быть целым числом")
            if not 1 <= self.intensity <= 5:
                raise ValueError("intensity должен находиться в диапазоне 1–5")


@dataclass(frozen=True, slots=True)
class SampleEventPayload:
    sample_code: str
    sample_kind: str | None = None
    bottom_depth_m: float | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text(self.sample_code, "sample_code")
        _validate_optional_text(self.sample_kind, "sample_kind")
        _validate_optional_non_negative(self.bottom_depth_m, "bottom_depth_m")
        _validate_optional_text(self.description, "description")


@dataclass(frozen=True, slots=True)
class CasingEventPayload:
    casing_type: str
    outer_diameter_mm: float
    shoe_depth_m: float | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text(self.casing_type, "casing_type")
        _validate_positive(self.outer_diameter_mm, "outer_diameter_mm")
        _validate_optional_non_negative(self.shoe_depth_m, "shoe_depth_m")
        _validate_optional_text(self.status, "status")


@dataclass(frozen=True, slots=True)
class FormationTopEventPayload:
    formation_code: str
    formation_name: str | None = None
    confidence: float | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        _validate_required_text(self.formation_code, "formation_code")
        _validate_optional_text(self.formation_name, "formation_name")
        _validate_optional_range(self.confidence, "confidence", 0.0, 1.0)
        _validate_optional_text(self.description, "description")


OperationalEventPayload: TypeAlias = (
    DrillingEventPayload
    | GasEventPayload
    | ShowEventPayload
    | SampleEventPayload
    | CasingEventPayload
    | FormationTopEventPayload
)

_PAYLOAD_TYPE_BY_KIND: dict[OperationalEventKind, type[OperationalEventPayload]] = {
    OperationalEventKind.DRILLING: DrillingEventPayload,
    OperationalEventKind.GAS: GasEventPayload,
    OperationalEventKind.SHOW: ShowEventPayload,
    OperationalEventKind.SAMPLE: SampleEventPayload,
    OperationalEventKind.CASING: CasingEventPayload,
    OperationalEventKind.FORMATION_TOP: FormationTopEventPayload,
}


@dataclass(frozen=True, slots=True)
class OperationalEvent:
    event_id: str
    well_id: str
    kind: OperationalEventKind
    payload: OperationalEventPayload
    depth_m: float | None = None
    elapsed_time_s: float | None = None
    measured_at: str | None = None
    received_at: str | None = None
    source: str = "manual"
    revision: int = 1
    calibration_id: str | None = None
    calibrated_at: str | None = None
    qc_flags: tuple[OperationalEventQcFlag, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_required_text(self.event_id, "event_id")
        _validate_required_text(self.well_id, "well_id")
        if not isinstance(self.kind, OperationalEventKind):
            raise ValueError("kind должен использовать OperationalEventKind")
        expected_payload_type = _PAYLOAD_TYPE_BY_KIND[self.kind]
        if not isinstance(self.payload, expected_payload_type):
            payload_name = type(self.payload).__name__
            raise ValueError(
                f"Payload типа {payload_name} не соответствует событию {self.kind.value}"
            )
        _validate_optional_non_negative(self.depth_m, "depth_m")
        _validate_optional_non_negative(self.elapsed_time_s, "elapsed_time_s")
        measured_at = _canonical_timestamp(self.measured_at, "measured_at")
        received_at = _canonical_timestamp(self.received_at, "received_at")
        calibrated_at = _canonical_timestamp(self.calibrated_at, "calibrated_at")
        object.__setattr__(self, "measured_at", measured_at)
        object.__setattr__(self, "received_at", received_at)
        object.__setattr__(self, "calibrated_at", calibrated_at)
        if self.depth_m is None and self.elapsed_time_s is None and measured_at is None:
            raise ValueError("Operational event требует depth_m, elapsed_time_s или measured_at")
        if (
            isinstance(self.payload, SampleEventPayload)
            and self.depth_m is not None
            and self.payload.bottom_depth_m is not None
            and self.payload.bottom_depth_m < self.depth_m
        ):
            raise ValueError("bottom_depth_m пробы не может быть меньше depth_m события")
        _validate_required_text(self.source, "source")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise ValueError("revision должен быть целым числом")
        if self.revision < 1:
            raise ValueError("revision должен быть положительным")
        _validate_optional_text(self.calibration_id, "calibration_id")
        if calibrated_at is not None and self.calibration_id is None:
            raise ValueError("calibrated_at нельзя задавать без calibration_id")
        if not isinstance(self.qc_flags, tuple) or not all(
            isinstance(flag, OperationalEventQcFlag) for flag in self.qc_flags
        ):
            raise ValueError("qc_flags должен быть tuple OperationalEventQcFlag")
        normalized_flags = tuple(sorted(set(self.qc_flags), key=str))
        object.__setattr__(self, "qc_flags", normalized_flags)

    @property
    def primary_anchor(self) -> tuple[str, float | str]:
        if self.depth_m is not None:
            return "depth", self.depth_m
        if self.elapsed_time_s is not None:
            return "elapsed_time", self.elapsed_time_s
        assert self.measured_at is not None
        return "datetime", self.measured_at


def operational_event_sort_key(event: OperationalEvent) -> tuple[int, float | str, str, str]:
    anchor_kind, anchor_value = event.primary_anchor
    priority = {"depth": 0, "elapsed_time": 1, "datetime": 2}[anchor_kind]
    return priority, anchor_value, event.received_at or "", event.event_id


def parse_operational_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp должен содержать часовой пояс")
    return parsed.astimezone(timezone.utc)


def _canonical_timestamp(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} должен быть непустой строкой")
    try:
        parsed = parse_operational_timestamp(value.strip())
    except ValueError as exc:
        raise ValueError(f"{name} должен быть ISO-8601 timestamp с часовым поясом") from exc
    return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _validate_required_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} должен быть непустой строкой")


def _validate_optional_text(value: object, name: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{name} должен быть непустой строкой или None")


def _validate_positive(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} должен быть числом")
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f"{name} должен быть конечным положительным числом")


def _validate_optional_non_negative(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} должен быть числом или None")
    numeric = float(value)
    if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f"{name} должен быть конечным неотрицательным числом")


def _validate_optional_range(
    value: object,
    name: str,
    minimum: float,
    maximum: float,
) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} должен быть числом или None")
    numeric = float(value)
    if not isfinite(numeric) or not minimum <= numeric <= maximum:
        raise ValueError(f"{name} должен находиться в диапазоне {minimum}–{maximum}")
