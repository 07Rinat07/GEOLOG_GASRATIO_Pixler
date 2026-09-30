from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from geoworkbench.acquisition.wits0_live_alarms import Wits0LiveAlarmController
from geoworkbench.acquisition.wits0_live_forms import Wits0SavedAlarmRule
from geoworkbench.domain.acquisition import (
    AcquisitionDataRowPayload,
    AcquisitionRecord,
    AcquisitionRecordKind,
)
from geoworkbench.domain.models import CurveData, CurveMetadata
from geoworkbench.services.acquisition_live_view import (
    AcquisitionCurrentValue,
    AcquisitionLiveQuality,
)
from geoworkbench.services.wits0_alarms import AlarmSide, AlarmTransition


@dataclass
class _SessionStub:
    records: list[AcquisitionRecord] = field(default_factory=list)

    @property
    def last_sequence(self) -> int:
        return self.records[-1].sequence if self.records else 0


def _record(
    sequence: int,
    values: tuple[tuple[str, float | None], ...],
    *,
    record_no: int = 1,
) -> AcquisitionRecord:
    return AcquisitionRecord(
        record_id=f"record-{sequence}",
        sequence=sequence,
        kind=AcquisitionRecordKind.DATA_ROW,
        payload=AcquisitionDataRowPayload(
            index_values=(("time", sequence),),
            curve_values=values,
        ),
        received_at=f"2026-09-30T12:00:{sequence:02d}Z",
        source=f"wits0:record={record_no:02d}",
    )


def _value(
    value: float | None,
    *,
    row: int,
    sample_row: int | None = None,
    quality: AcquisitionLiveQuality = AcquisitionLiveQuality.GOOD,
    curve_id: str = "curve-tg",
    mnemonic: str = "TOTAL_GAS",
) -> AcquisitionCurrentValue:
    resolved_sample = row if sample_row is None and value is not None else sample_row
    return AcquisitionCurrentValue(
        curve_id=curve_id,
        mnemonic=mnemonic,
        unit="%",
        value=value,
        quality=quality,
        quality_codes=(quality.value,),
        sample_row_index=resolved_sample,
        latest_row_index=row,
        axis_value=float(resolved_sample) if resolved_sample is not None else None,
        received_at=None,
        source_sequence_no=resolved_sample,
        age_rows=(row - resolved_sample) if resolved_sample is not None else None,
    )


def _evaluate(
    controller: Wits0LiveAlarmController,
    session: _SessionStub,
    values: tuple[AcquisitionCurrentValue, ...],
    *,
    virtual_curves: dict[str, CurveData] | None = None,
) -> tuple:
    row_count = sum(
        record.kind is AcquisitionRecordKind.DATA_ROW
        for record in session.records
    )
    return controller.evaluate(
        session,  # type: ignore[arg-type] - minimal append-only session stub
        values,
        virtual_curves=virtual_curves,
        dataset_row_count=row_count,
    )


def _derived_curve(
    values: tuple[float, ...],
    *,
    curve_id: str = "derived-dexp",
) -> CurveData:
    return CurveData(
        metadata=CurveMetadata(
            curve_id=curve_id,
            original_mnemonic="DEXP",
            canonical_mnemonic="DEXP",
            unit="1",
            description="Derived D exponent",
            source_dataset_id="dataset-1",
            provenance="formula:test.dexp:1;source-records=01",
        ),
        values=np.asarray(values, dtype=np.float64),
    )


def test_runtime_debounce_advances_once_per_factual_sample() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (Wits0SavedAlarmRule(mnemonic="total_gas", maximum=5.0, debounce_samples=2),)
    )
    session = _SessionStub([_record(1, (("curve-tg", 6.0),))])

    first = _evaluate(controller, session, (_value(6.0, row=0),))
    repeated = _evaluate(controller, session, (_value(6.0, row=0),))
    session.records.append(_record(2, (("curve-tg", 6.5),)))
    second = _evaluate(controller, session, (_value(6.5, row=1),))

    assert not first[0].is_active
    assert not repeated[0].is_active
    assert second[0].active_side is AlarmSide.HIGH
    assert second[0].needs_attention


def test_runtime_catches_up_every_drained_sample_while_view_is_frozen() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (Wits0SavedAlarmRule(mnemonic="TOTAL_GAS", maximum=5.0, debounce_samples=3),)
    )
    session = _SessionStub([_record(1, (("curve-tg", 6.0),))])
    frozen = _value(6.0, row=0)

    assert not _evaluate(controller, session, (frozen,))[0].is_active

    session.records.extend(
        (
            _record(2, (("curve-tg", 6.1),)),
            _record(3, (("curve-tg", 6.2),)),
        )
    )
    caught_up = _evaluate(controller, session, (frozen,))

    assert caught_up[0].active_side is AlarmSide.HIGH
    assert caught_up[0].needs_attention


def test_explicit_missing_sample_resets_pending_without_clearing_active_alarm() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (Wits0SavedAlarmRule(mnemonic="TOTAL_GAS", maximum=5.0, debounce_samples=2),)
    )
    session = _SessionStub([_record(1, (("curve-tg", 6.0),))])
    _evaluate(controller, session, (_value(6.0, row=0),))

    session.records.append(_record(2, (("curve-tg", None),)))
    missing = _evaluate(
        controller,
        session,
        (
            _value(
                6.0,
                row=1,
                sample_row=0,
                quality=AcquisitionLiveQuality.MISSING,
            ),
        ),
    )
    session.records.append(_record(3, (("curve-tg", 6.2),)))
    after_gap = _evaluate(controller, session, (_value(6.2, row=2),))
    session.records.append(_record(4, (("curve-tg", 6.4),)))
    active = _evaluate(controller, session, (_value(6.4, row=3),))

    assert not missing[0].is_active
    assert not after_gap[0].is_active
    assert active[0].is_active

    session.records.append(_record(5, (("curve-tg", None),)))
    preserved = _evaluate(
        controller,
        session,
        (
            _value(
                6.4,
                row=4,
                sample_row=3,
                quality=AcquisitionLiveQuality.MISSING,
            ),
        ),
    )
    assert preserved[0].is_active


def test_acknowledge_all_preserves_active_alarm_and_clears_attention() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (
            Wits0SavedAlarmRule(
                mnemonic="TOTAL_GAS",
                maximum=5.0,
                visual_enabled=True,
                audio_enabled=True,
            ),
        )
    )
    session = _SessionStub([_record(1, (("curve-tg", 7.0),))])
    active = _evaluate(controller, session, (_value(7.0, row=0),))
    assert active[0].needs_attention

    assert controller.acknowledge_all() == 1
    acknowledged = _evaluate(controller, session, (_value(7.0, row=0),))

    assert acknowledged[0].is_active
    assert acknowledged[0].acknowledged
    assert not acknowledged[0].needs_attention
    assert acknowledged[0].visual_enabled
    assert acknowledged[0].audio_enabled


def test_changed_rule_resets_previous_runtime_state() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules((Wits0SavedAlarmRule(mnemonic="TOTAL_GAS", maximum=5.0),))
    session = _SessionStub([_record(1, (("curve-tg", 7.0),))])
    assert _evaluate(controller, session, (_value(7.0, row=0),))[0].is_active

    controller.set_rules((Wits0SavedAlarmRule(mnemonic="TOTAL_GAS", maximum=10.0),))
    status = _evaluate(controller, session, (_value(7.0, row=0),))

    assert not status[0].is_active


def test_duplicate_mnemonic_curves_do_not_share_debounce_state() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (Wits0SavedAlarmRule(mnemonic="TOTAL_GAS", maximum=5.0, debounce_samples=2),)
    )
    session = _SessionStub(
        [_record(1, (("gas-a", 6.0), ("gas-b", 7.0)))]
    )
    first = _evaluate(
        controller,
        session,
        (
            _value(6.0, row=0, curve_id="gas-a"),
            _value(7.0, row=0, curve_id="gas-b"),
        ),
    )
    assert all(not status.is_active for status in first)

    session.records.append(
        _record(2, (("gas-a", 6.1), ("gas-b", 7.1)))
    )
    second = _evaluate(
        controller,
        session,
        (
            _value(6.1, row=1, curve_id="gas-a"),
            _value(7.1, row=1, curve_id="gas-b"),
        ),
    )
    assert {status.curve_id for status in second if status.is_active} == {
        "gas-a",
        "gas-b",
    }


def test_unrelated_data_row_does_not_break_channel_debounce() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (Wits0SavedAlarmRule(mnemonic="TOTAL_GAS", maximum=5.0, debounce_samples=2),)
    )
    session = _SessionStub([_record(1, (("curve-tg", 6.0),))])
    _evaluate(controller, session, (_value(6.0, row=0),))

    session.records.extend(
        (
            _record(2, (("other-curve", 100.0),)),
            _record(3, (("curve-tg", 6.5),)),
        )
    )
    status = _evaluate(controller, session, (_value(6.5, row=2),))

    assert status[0].is_active



def test_derived_alarm_catches_up_each_relevant_source_record() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (Wits0SavedAlarmRule(mnemonic="DEXP", maximum=5.0, debounce_samples=3),)
    )
    session = _SessionStub([_record(1, (("source-rop", 10.0),), record_no=1)])
    frozen = _value(
        6.0,
        row=0,
        curve_id="derived-dexp",
        mnemonic="DEXP",
    )

    first_curve = _derived_curve((6.0,))
    first = _evaluate(
        controller,
        session,
        (frozen,),
        virtual_curves={first_curve.metadata.curve_id: first_curve},
    )
    assert not first[0].is_active

    session.records.extend(
        (
            _record(2, (("source-rop", 11.0),), record_no=1),
            _record(3, (("source-rop", 12.0),), record_no=1),
        )
    )
    updated_curve = _derived_curve((6.0, 6.1, 6.2))
    caught_up = _evaluate(
        controller,
        session,
        (frozen,),
        virtual_curves={updated_curve.metadata.curve_id: updated_curve},
    )

    assert caught_up[0].active_side is AlarmSide.HIGH
    assert caught_up[0].needs_attention


def test_derived_alarm_ignores_unrelated_wits_record_rows() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (Wits0SavedAlarmRule(mnemonic="DEXP", maximum=5.0, debounce_samples=2),)
    )
    session = _SessionStub([_record(1, (("source-rop", 10.0),), record_no=1)])
    frozen = _value(
        6.0,
        row=0,
        curve_id="derived-dexp",
        mnemonic="DEXP",
    )
    initial_curve = _derived_curve((6.0,))
    _evaluate(
        controller,
        session,
        (frozen,),
        virtual_curves={initial_curve.metadata.curve_id: initial_curve},
    )

    session.records.extend(
        (
            _record(2, (("unrelated", 999.0),), record_no=2),
            _record(3, (("source-rop", 11.0),), record_no=1),
        )
    )
    updated_curve = _derived_curve((6.0, 999.0, 6.2))
    status = _evaluate(
        controller,
        session,
        (frozen,),
        virtual_curves={updated_curve.metadata.curve_id: updated_curve},
    )

    assert status[0].is_active


def test_runtime_records_every_factual_activation_and_clear_in_batch() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (
            Wits0SavedAlarmRule(
                mnemonic="TOTAL_GAS",
                maximum=5.0,
                debounce_samples=1,
                visual_enabled=True,
                audio_enabled=True,
            ),
        )
    )
    session = _SessionStub([_record(1, (("curve-tg", 4.0),))])

    _evaluate(controller, session, (_value(4.0, row=0),))
    assert controller.latest_events == ()
    assert controller.event_history == ()

    session.records.extend(
        (
            _record(2, (("curve-tg", 6.0),)),
            _record(3, (("curve-tg", 4.0),)),
            _record(4, (("curve-tg", 7.0),)),
        )
    )
    _evaluate(controller, session, (_value(7.0, row=3),))

    events = controller.latest_events
    assert [event.transition for event in events] == [
        AlarmTransition.ACTIVATED,
        AlarmTransition.CLEARED,
        AlarmTransition.ACTIVATED,
    ]
    assert [event.row_index for event in events] == [1, 2, 3]
    assert [event.record_sequence for event in events] == [2, 3, 4]
    assert [event.side for event in events] == [
        AlarmSide.HIGH,
        AlarmSide.HIGH,
        AlarmSide.HIGH,
    ]
    assert [event.value for event in events] == [6.0, 4.0, 7.0]
    assert all(event.threshold == 5.0 for event in events)
    assert all(event.visual_enabled for event in events)
    assert all(event.audio_enabled for event in events)
    assert controller.event_history == events

    _evaluate(controller, session, (_value(7.0, row=3),))
    assert controller.latest_events == ()
    assert controller.event_history == events


def test_runtime_event_history_is_bounded_and_rule_change_drops_old_events() -> None:
    controller = Wits0LiveAlarmController(max_event_history=2)
    controller.set_rules(
        (
            Wits0SavedAlarmRule(
                mnemonic="TOTAL_GAS",
                maximum=5.0,
                debounce_samples=1,
            ),
        )
    )
    session = _SessionStub([_record(1, (("curve-tg", 4.0),))])
    _evaluate(controller, session, (_value(4.0, row=0),))

    session.records.extend(
        (
            _record(2, (("curve-tg", 6.0),)),
            _record(3, (("curve-tg", 4.0),)),
            _record(4, (("curve-tg", 7.0),)),
        )
    )
    _evaluate(controller, session, (_value(7.0, row=3),))

    assert [event.row_index for event in controller.event_history] == [2, 3]

    controller.set_rules(
        (
            Wits0SavedAlarmRule(
                mnemonic="TOTAL_GAS",
                maximum=10.0,
                debounce_samples=1,
            ),
        )
    )
    assert controller.event_history == ()
    assert controller.latest_events == ()


def test_runtime_does_not_fabricate_audio_or_marker_event_when_rule_is_seeded() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (
            Wits0SavedAlarmRule(
                mnemonic="TOTAL_GAS",
                maximum=5.0,
                debounce_samples=1,
                audio_enabled=True,
            ),
        )
    )
    session = _SessionStub([_record(1, (("curve-tg", 9.0),))])

    status = _evaluate(controller, session, (_value(9.0, row=0),))

    assert status[0].is_active
    assert controller.latest_events == ()
    assert controller.event_history == ()
