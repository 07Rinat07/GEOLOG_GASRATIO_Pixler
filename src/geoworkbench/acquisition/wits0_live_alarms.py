from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable, Mapping
from math import isfinite

from geoworkbench.acquisition.wits0_live_forms import Wits0SavedAlarmRule
from geoworkbench.domain.acquisition import (
    AcquisitionDataRowPayload,
    AcquisitionRecordKind,
    AcquisitionSession,
)
from geoworkbench.catalogs.sensors import normalize_sensor_key
from geoworkbench.domain.models import CurveData
from geoworkbench.services.acquisition_live_view import (
    AcquisitionCurrentValue,
    AcquisitionLiveQuality,
    wits0_source_record_no,
    wits0_virtual_source_record_numbers,
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
        *,
        virtual_curves: Mapping[str, CurveData] | None = None,
        dataset_row_count: int,
    ) -> tuple[Wits0LiveAlarmStatus, ...]:
        if (
            isinstance(dataset_row_count, bool)
            or not isinstance(dataset_row_count, int)
            or dataset_row_count < 0
        ):
            raise ValueError("dataset_row_count must be a non-negative integer")

        virtual = dict(virtual_curves or {})
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
            if earliest < 0 or earliest > session.last_sequence:
                raise ValueError("alarm runtime sequence is outside acquisition session")
            tail_records = session.records[earliest:]
            tail_data_rows = sum(
                record.kind is AcquisitionRecordKind.DATA_ROW
                for record in tail_records
            )
            first_tail_row = dataset_row_count - tail_data_rows
            if first_tail_row < 0:
                raise ValueError(
                    "dataset row count is smaller than appended acquisition DATA_ROW tail"
                )

            data_row_index = first_tail_row
            virtual_sources = {
                curve_id: wits0_virtual_source_record_numbers(
                    curve.metadata.provenance
                )
                for curve_id, curve in virtual.items()
                if curve_id in catch_up
            }
            for record in tail_records:
                if record.kind is not AcquisitionRecordKind.DATA_ROW:
                    continue
                if not isinstance(record.payload, AcquisitionDataRowPayload):
                    continue
                if data_row_index >= dataset_row_count:
                    raise ValueError(
                        "acquisition DATA_ROW tail exceeds dataset row count"
                    )
                row_values = record.payload.curves_dict()
                record_no = wits0_source_record_no(record.source)
                for curve_id, (_item, _key, rule) in catch_up.items():
                    if record.sequence <= self._last_sequences[curve_id]:
                        continue
                    sample = _sample_from_data_row(
                        curve_id,
                        row_values,
                        record_no=record_no,
                        data_row_index=data_row_index,
                        virtual_curve=virtual.get(curve_id),
                        virtual_source_records=virtual_sources.get(
                            curve_id,
                            frozenset(),
                        ),
                    )
                    if sample is _NO_SAMPLE:
                        continue
                    evaluation = evaluate_alarm(
                        _limits(rule),
                        self._states.get(curve_id, AlarmState()),
                        sample,
                    )
                    self._states[curve_id] = evaluation.state
                    if evaluation.transition is not AlarmTransition.NONE:
                        transitions[curve_id] = evaluation.transition
                data_row_index += 1

            if data_row_index != dataset_row_count:
                raise ValueError(
                    "acquisition DATA_ROW tail does not align with dataset rows"
                )
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


_NO_SAMPLE = object()


def _sample_from_data_row(
    curve_id: str,
    row_values: Mapping[str, float | None],
    *,
    record_no: int | None,
    data_row_index: int,
    virtual_curve: CurveData | None,
    virtual_source_records: frozenset[int],
) -> float | None | object:
    if curve_id in row_values:
        return row_values[curve_id]
    if (
        virtual_curve is None
        or not virtual_source_records
        or record_no not in virtual_source_records
    ):
        return _NO_SAMPLE
    if data_row_index >= len(virtual_curve.values):
        raise ValueError("derived alarm curve does not align with dataset rows")
    value = float(virtual_curve.values[data_row_index])
    return value if isfinite(value) else None


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
