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

    def set_rules(self, rules: Iterable[Wits0SavedAlarmRule]) -> None:
        materialized = tuple(rules)
        updated = {
            normalize_sensor_key(rule.mnemonic): rule
            for rule in materialized
            if normalize_sensor_key(rule.mnemonic)
        }
        if len(updated) != len(materialized):
            raise ValueError("alarm rules must have unique valid mnemonics")

        preserved_states: dict[str, AlarmState] = {}
        preserved_tokens: dict[str, tuple[object, ...]] = {}
        for key, rule in updated.items():
            if self._rules.get(key) != rule:
                continue
            if key in self._states:
                preserved_states[key] = self._states[key]
            if key in self._last_tokens:
                preserved_tokens[key] = self._last_tokens[key]

        self._rules = updated
        self._states = preserved_states
        self._last_tokens = preserved_tokens

    def clear(self) -> None:
        self._rules.clear()
        self._states.clear()
        self._last_tokens.clear()

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

            state = self._states.get(key, AlarmState())
            transition = AlarmTransition.NONE
            event = _evaluation_event(item)
            if event is not None:
                token, sample = event
                if self._last_tokens.get(key) != token:
                    evaluation = evaluate_alarm(_limits(rule), state, sample)
                    state = evaluation.state
                    transition = evaluation.transition
                    self._states[key] = state
                    self._last_tokens[key] = token

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

    def acknowledge(self, mnemonic: str) -> bool:
        key = normalize_sensor_key(mnemonic)
        state = self._states.get(key)
        if state is None:
            return False
        evaluation = acknowledge_alarm(state)
        if evaluation.transition is not AlarmTransition.ACKNOWLEDGED:
            return False
        self._states[key] = evaluation.state
        return True

    def acknowledge_all(self) -> int:
        count = 0
        for key, state in tuple(self._states.items()):
            evaluation = acknowledge_alarm(state)
            if evaluation.transition is not AlarmTransition.ACKNOWLEDGED:
                continue
            self._states[key] = evaluation.state
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
