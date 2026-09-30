from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from geoworkbench.acquisition.wits0_live_forms import Wits0SavedAlarmRule
from geoworkbench.domain.acquisition import (
    AcquisitionDataRowPayload,
    AcquisitionRecordKind,
    AcquisitionSession,
)
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

    UI refresh cadence is intentionally irrelevant to debounce. New append-only
    acquisition DATA_ROW records are replayed from the last processed session
    sequence for each displayed curve, so a drained batch cannot collapse into one
    debounce sample and screen Pause cannot suspend alarm evaluation. Explicit None
    values reset only an uncommitted debounce sequence while preserving active alarms.
    """

    def __init__(self) -> None:
        self._rules: dict[str, Wits0SavedAlarmRule] = {}
        self._states: dict[str, AlarmState] = {}
        self._last_sequences: dict[str, int] = {}
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
        self._last_sequences = {
            curve_id: sequence
            for curve_id, sequence in self._last_sequences.items()
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
        self._last_sequences.clear()
        self._state_rule_keys.clear()
        self._state_rules.clear()

    def evaluate(
        self,
        session: AcquisitionSession,
        values: Iterable[AcquisitionCurrentValue],
    ) -> tuple[Wits0LiveAlarmStatus, ...]:
        materialized = tuple(values)
        configured: dict[
            str,
            tuple[AcquisitionCurrentValue, str, Wits0SavedAlarmRule],
        ] = {}
        transitions: dict[str, AlarmTransition] = {}

        for item in materialized:
            key = normalize_sensor_key(item.mnemonic)
            rule = self._rules.get(key)
            if rule is None:
                continue
            curve_id = item.curve_id
            configured[curve_id] = (item, key, rule)
            if (
                self._state_rule_keys.get(curve_id) == key
                and self._state_rules.get(curve_id) == rule
            ):
                continue

            self._states.pop(curve_id, None)
            self._last_sequences.pop(curve_id, None)
            self._state_rule_keys[curve_id] = key
            self._state_rules[curve_id] = rule
            initial_sample = (
                None
                if item.quality
                in {
                    AcquisitionLiveQuality.MISSING,
                    AcquisitionLiveQuality.INVALID,
                }
                else item.value
            )
            evaluation = evaluate_alarm(_limits(rule), AlarmState(), initial_sample)
            self._states[curve_id] = evaluation.state
            self._last_sequences[curve_id] = session.last_sequence
            transitions[curve_id] = evaluation.transition

        catch_up = {
            curve_id: payload
            for curve_id, payload in configured.items()
            if curve_id in self._last_sequences
        }
        if catch_up:
            earliest = min(self._last_sequences[curve_id] for curve_id in catch_up)
            for record in session.records:
                if record.sequence <= earliest:
                    continue
                if (
                    record.kind is not AcquisitionRecordKind.DATA_ROW
                    or not isinstance(record.payload, AcquisitionDataRowPayload)
                ):
                    continue
                row_values = record.payload.curves_dict()
                for curve_id, (_item, _key, rule) in catch_up.items():
                    if record.sequence <= self._last_sequences[curve_id]:
                        continue
                    if curve_id not in row_values:
                        continue
                    evaluation = evaluate_alarm(
                        _limits(rule),
                        self._states.get(curve_id, AlarmState()),
                        row_values[curve_id],
                    )
                    self._states[curve_id] = evaluation.state
                    if evaluation.transition is not AlarmTransition.NONE:
                        transitions[curve_id] = evaluation.transition
            for curve_id in catch_up:
                self._last_sequences[curve_id] = session.last_sequence

        statuses: list[Wits0LiveAlarmStatus] = []
        for item in materialized:
            key = normalize_sensor_key(item.mnemonic)
            rule = self._rules.get(key)
            if rule is None:
                continue
            state = self._states.get(item.curve_id, AlarmState())
            statuses.append(
                Wits0LiveAlarmStatus(
                    curve_id=item.curve_id,
                    mnemonic=item.mnemonic,
                    active_side=state.active_side,
                    acknowledged=state.acknowledged,
                    transition=transitions.get(
                        item.curve_id,
                        AlarmTransition.NONE,
                    ),
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


__all__ = [
    "Wits0LiveAlarmController",
    "Wits0LiveAlarmStatus",
]
