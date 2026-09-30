from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from geoworkbench.acquisition.wits0_live_forms import Wits0SavedAlarmRule
from geoworkbench.catalogs.sensors import normalize_sensor_key
from geoworkbench.services.acquisition_live_view import (
    AcquisitionCurrentValue,
    AcquisitionLiveQuality,
)
from geoworkbench.services.wits0_alarms import (
    AlarmLimits,
    AlarmSide,
    AlarmState,
    AlarmTransition,
    acknowledge_alarm,
    evaluate_alarm,
)


@dataclass(frozen=True, slots=True)
class Wits0LiveAlarmStatus:
    curve_id: str
    mnemonic: str
    active_side: AlarmSide | None
    acknowledged: bool
    transition: AlarmTransition
    visual_enabled: bool
    audio_enabled: bool

    @property
    def is_active(self) -> bool:
        return self.active_side is not None

    @property
    def needs_attention(self) -> bool:
        return self.is_active and not self.acknowledged


class Wits0LiveAlarmController:
    """Evaluate configured WITS alarm rules once per factual live sample.

    UI refresh cadence is intentionally irrelevant to debounce. A repeated snapshot
    keeps the existing state because it carries the same sample identity. Missing or
    invalid relevant rows are evaluated as missing input once for that row, which
    resets only an uncommitted debounce sequence while preserving active alarms.
    """

    def __init__(self) -> None:
        self._rules: dict[str, Wits0SavedAlarmRule] = {}
        self._states: dict[str, AlarmState] = {}
        self._last_tokens: dict[str, tuple[object, ...]] = {}
        self._state_rule_keys: dict[str, str] = {}
        self._state_rules: dict[str, Wits0SavedAlarmRule] = {}

    def set_rules(self, rules: Iterable[Wits0SavedAlarmRule]) -> None:
        materialized = tuple(rules)
        updated = {
            normalize_sensor_key(rule.mnemonic): rule
            for rule in materialized
            if normalize_sensor_key(rule.mnemonic)
        }
        if len(updated) != len(materialized):
            raise ValueError("alarm rules must have unique valid mnemonics")

        preserved_curve_ids = {
            curve_id
            for curve_id, key in self._state_rule_keys.items()
            if key in updated and self._state_rules.get(curve_id) == updated[key]
        }
        self._rules = updated
        self._states = {
            curve_id: state
            for curve_id, state in self._states.items()
            if curve_id in preserved_curve_ids
        }
        self._last_tokens = {
            curve_id: token
            for curve_id, token in self._last_tokens.items()
            if curve_id in preserved_curve_ids
        }
        self._state_rule_keys = {
            curve_id: key
            for curve_id, key in self._state_rule_keys.items()
            if curve_id in preserved_curve_ids
        }
        self._state_rules = {
            curve_id: rule
            for curve_id, rule in self._state_rules.items()
            if curve_id in preserved_curve_ids
        }

    def clear(self) -> None:
        self._rules.clear()
        self._states.clear()
        self._last_tokens.clear()
        self._state_rule_keys.clear()
        self._state_rules.clear()

    def evaluate(
        self,
        values: Iterable[AcquisitionCurrentValue],
    ) -> tuple[Wits0LiveAlarmStatus, ...]:
        statuses: list[Wits0LiveAlarmStatus] = []
        for item in values:
            key = normalize_sensor_key(item.mnemonic)
            rule = self._rules.get(key)
            if rule is None:
                continue

            curve_id = item.curve_id
            if (
                self._state_rule_keys.get(curve_id) != key
                or self._state_rules.get(curve_id) != rule
            ):
                self._states.pop(curve_id, None)
                self._last_tokens.pop(curve_id, None)
            self._state_rule_keys[curve_id] = key
            self._state_rules[curve_id] = rule

            state = self._states.get(curve_id, AlarmState())
            transition = AlarmTransition.NONE
            event = _evaluation_event(item)
            if event is not None:
                token, sample = event
                if self._last_tokens.get(curve_id) != token:
                    evaluation = evaluate_alarm(_limits(rule), state, sample)
                    state = evaluation.state
                    transition = evaluation.transition
                    self._states[curve_id] = state
                    self._last_tokens[curve_id] = token

            statuses.append(
                Wits0LiveAlarmStatus(
                    curve_id=item.curve_id,
                    mnemonic=item.mnemonic,
                    active_side=state.active_side,
                    acknowledged=state.acknowledged,
                    transition=transition,
                    visual_enabled=rule.visual_enabled,
                    audio_enabled=rule.audio_enabled,
                )
            )
        return tuple(statuses)

    def acknowledge(self, mnemonic: str) -> int:
        key = normalize_sensor_key(mnemonic)
        count = 0
        for curve_id, state in tuple(self._states.items()):
            if self._state_rule_keys.get(curve_id) != key:
                continue
            evaluation = acknowledge_alarm(state)
            if evaluation.transition is not AlarmTransition.ACKNOWLEDGED:
                continue
            self._states[curve_id] = evaluation.state
            count += 1
        return count

    def acknowledge_all(self) -> int:
        count = 0
        for curve_id, state in tuple(self._states.items()):
            evaluation = acknowledge_alarm(state)
            if evaluation.transition is not AlarmTransition.ACKNOWLEDGED:
                continue
            self._states[curve_id] = evaluation.state
            count += 1
        return count


def _limits(rule: Wits0SavedAlarmRule) -> AlarmLimits:
    return AlarmLimits(
        minimum=rule.minimum,
        maximum=rule.maximum,
        hysteresis=rule.hysteresis,
        debounce_samples=rule.debounce_samples,
    )


def _evaluation_event(
    value: AcquisitionCurrentValue,
) -> tuple[tuple[object, ...], float | None] | None:
    if value.latest_row_index is None:
        return None
    if value.quality in {
        AcquisitionLiveQuality.MISSING,
        AcquisitionLiveQuality.INVALID,
    }:
        return (
            ("missing", value.latest_row_index, value.quality.value),
            None,
        )
    if value.sample_row_index is None:
        return None
    return (
        (
            "sample",
            value.sample_row_index,
            value.source_sequence_no,
        ),
        value.value,
    )


__all__ = [
    "Wits0LiveAlarmController",
    "Wits0LiveAlarmStatus",
]
