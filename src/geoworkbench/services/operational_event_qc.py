from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import timedelta
from math import isfinite
from typing import Iterable

from geoworkbench.domain.operational_events import (
    OperationalEvent,
    OperationalEventKind,
    OperationalEventQcFlag,
    parse_operational_timestamp,
)


@dataclass(frozen=True, slots=True)
class OperationalEventQcPolicy:
    max_depth_gap_m: float = 30.0
    max_time_gap_s: float = 300.0
    stale_after_s: float = 120.0
    calibration_ttl_s: float = 86_400.0
    calibration_required_kinds: tuple[OperationalEventKind, ...] = (
        OperationalEventKind.GAS,
    )

    def __post_init__(self) -> None:
        for name, value in (
            ("max_depth_gap_m", self.max_depth_gap_m),
            ("max_time_gap_s", self.max_time_gap_s),
            ("stale_after_s", self.stale_after_s),
            ("calibration_ttl_s", self.calibration_ttl_s),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(float(value))
                or value <= 0.0
            ):
                raise ValueError(f"{name} должен быть положительным числом")
        if not isinstance(self.calibration_required_kinds, tuple) or not all(
            isinstance(kind, OperationalEventKind) for kind in self.calibration_required_kinds
        ):
            raise ValueError("calibration_required_kinds имеет неверный тип")


class OperationalEventQcEvaluator:
    """Deterministically calculate QC flags for a complete well event collection."""

    def __init__(self, policy: OperationalEventQcPolicy | None = None) -> None:
        self.policy = policy or OperationalEventQcPolicy()

    def evaluate(
        self,
        events: Iterable[OperationalEvent],
    ) -> dict[str, tuple[OperationalEventQcFlag, ...]]:
        event_list = list(events)
        flags: dict[str, set[OperationalEventQcFlag]] = {
            event.event_id: set() for event in event_list
        }
        if len(flags) != len(event_list):
            raise ValueError("event_id должен быть уникальным в QC collection")

        self._mark_duplicates(event_list, flags)
        self._mark_out_of_order(event_list, flags)
        self._mark_gaps(event_list, flags)
        self._mark_stale(event_list, flags)
        self._mark_calibration(event_list, flags)

        return {
            event_id: tuple(sorted(event_flags, key=str))
            for event_id, event_flags in flags.items()
        }

    @staticmethod
    def _mark_duplicates(
        events: list[OperationalEvent],
        flags: dict[str, set[OperationalEventQcFlag]],
    ) -> None:
        groups: dict[str, list[OperationalEvent]] = {}
        for event in events:
            groups.setdefault(_duplicate_fingerprint(event), []).append(event)
        for duplicate_group in groups.values():
            if len(duplicate_group) < 2:
                continue
            for event in duplicate_group:
                flags[event.event_id].add(OperationalEventQcFlag.DUPLICATE)

    @staticmethod
    def _mark_out_of_order(
        events: list[OperationalEvent],
        flags: dict[str, set[OperationalEventQcFlag]],
    ) -> None:
        groups: dict[tuple[OperationalEventKind, str], list[OperationalEvent]] = {}
        for event in events:
            if event.received_at is None:
                continue
            anchor_kind, _value = event.primary_anchor
            groups.setdefault((event.kind, anchor_kind), []).append(event)
        for group in groups.values():
            ordered = sorted(group, key=lambda item: (item.received_at or "", item.event_id))
            highest: float | None = None
            for event in ordered:
                _anchor_kind, value = event.primary_anchor
                comparable = _anchor_comparable(value)
                if highest is not None and comparable < highest:
                    flags[event.event_id].add(OperationalEventQcFlag.OUT_OF_ORDER)
                if highest is None or comparable > highest:
                    highest = comparable

    def _mark_gaps(
        self,
        events: list[OperationalEvent],
        flags: dict[str, set[OperationalEventQcFlag]],
    ) -> None:
        groups: dict[tuple[OperationalEventKind, str], list[OperationalEvent]] = {}
        for event in events:
            anchor_kind, _value = event.primary_anchor
            groups.setdefault((event.kind, anchor_kind), []).append(event)
        for (_kind, anchor_kind), group in groups.items():
            ordered = sorted(
                group,
                key=lambda item: (_anchor_comparable(item.primary_anchor[1]), item.event_id),
            )
            threshold = (
                self.policy.max_depth_gap_m
                if anchor_kind == "depth"
                else self.policy.max_time_gap_s
            )
            previous_value: float | None = None
            for event in ordered:
                current_value = _anchor_numeric(event.primary_anchor[1])
                if previous_value is not None and current_value - previous_value > threshold:
                    flags[event.event_id].add(OperationalEventQcFlag.GAP)
                previous_value = current_value

    def _mark_stale(
        self,
        events: list[OperationalEvent],
        flags: dict[str, set[OperationalEventQcFlag]],
    ) -> None:
        threshold = timedelta(seconds=self.policy.stale_after_s)
        for event in events:
            if event.measured_at is None or event.received_at is None:
                continue
            delay = parse_operational_timestamp(event.received_at) - parse_operational_timestamp(
                event.measured_at
            )
            if delay > threshold:
                flags[event.event_id].add(OperationalEventQcFlag.STALE)

    def _mark_calibration(
        self,
        events: list[OperationalEvent],
        flags: dict[str, set[OperationalEventQcFlag]],
    ) -> None:
        required = set(self.policy.calibration_required_kinds)
        ttl = timedelta(seconds=self.policy.calibration_ttl_s)
        for event in events:
            if event.kind not in required:
                continue
            if event.calibration_id is None:
                flags[event.event_id].add(OperationalEventQcFlag.CALIBRATION_MISSING)
                continue
            if event.calibrated_at is None or event.measured_at is None:
                continue
            age = parse_operational_timestamp(event.measured_at) - parse_operational_timestamp(
                event.calibrated_at
            )
            if age > ttl:
                flags[event.event_id].add(OperationalEventQcFlag.CALIBRATION_EXPIRED)


def _duplicate_fingerprint(event: OperationalEvent) -> str:
    payload = {
        "kind": event.kind.value,
        "depth_m": event.depth_m,
        "elapsed_time_s": event.elapsed_time_s,
        "measured_at": event.measured_at,
        "payload": asdict(event.payload),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _anchor_comparable(value: float | str) -> float:
    if isinstance(value, str):
        return parse_operational_timestamp(value).timestamp()
    return float(value)


def _anchor_numeric(value: float | str) -> float:
    comparable = _anchor_comparable(value)
    return float(comparable)
