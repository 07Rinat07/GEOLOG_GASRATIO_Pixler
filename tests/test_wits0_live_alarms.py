from geoworkbench.acquisition.wits0_live_alarms import Wits0LiveAlarmController
from geoworkbench.acquisition.wits0_live_forms import Wits0SavedAlarmRule
from geoworkbench.services.acquisition_live_view import (
    AcquisitionCurrentValue,
    AcquisitionLiveQuality,
)
from geoworkbench.services.wits0_alarms import AlarmSide


def _value(
    value: float | None,
    *,
    row: int,
    sample_row: int | None = None,
    quality: AcquisitionLiveQuality = AcquisitionLiveQuality.GOOD,
) -> AcquisitionCurrentValue:
    resolved_sample = row if sample_row is None and value is not None else sample_row
    return AcquisitionCurrentValue(
        curve_id="curve-tg",
        mnemonic="TOTAL_GAS",
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


def test_runtime_debounce_advances_once_per_factual_sample() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (Wits0SavedAlarmRule(mnemonic="total_gas", maximum=5.0, debounce_samples=2),)
    )

    first = controller.evaluate((_value(6.0, row=10),))
    repeated = controller.evaluate((_value(6.0, row=10),))
    second = controller.evaluate((_value(6.5, row=11),))

    assert not first[0].is_active
    assert not repeated[0].is_active
    assert second[0].active_side is AlarmSide.HIGH
    assert second[0].needs_attention


def test_missing_relevant_row_resets_pending_without_clearing_active_alarm() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules(
        (Wits0SavedAlarmRule(mnemonic="TOTAL_GAS", maximum=5.0, debounce_samples=2),)
    )

    controller.evaluate((_value(6.0, row=1),))
    missing = controller.evaluate(
        (
            _value(
                6.0,
                row=2,
                sample_row=1,
                quality=AcquisitionLiveQuality.MISSING,
            ),
        )
    )
    after_gap = controller.evaluate((_value(6.2, row=3),))
    active = controller.evaluate((_value(6.4, row=4),))

    assert not missing[0].is_active
    assert not after_gap[0].is_active
    assert active[0].is_active

    preserved = controller.evaluate(
        (
            _value(
                6.4,
                row=5,
                sample_row=4,
                quality=AcquisitionLiveQuality.MISSING,
            ),
        )
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
    active = controller.evaluate((_value(7.0, row=1),))
    assert active[0].needs_attention

    assert controller.acknowledge_all() == 1
    acknowledged = controller.evaluate((_value(7.0, row=1),))

    assert acknowledged[0].is_active
    assert acknowledged[0].acknowledged
    assert not acknowledged[0].needs_attention
    assert acknowledged[0].visual_enabled
    assert acknowledged[0].audio_enabled


def test_changed_rule_resets_previous_runtime_state() -> None:
    controller = Wits0LiveAlarmController()
    controller.set_rules((Wits0SavedAlarmRule(mnemonic="TOTAL_GAS", maximum=5.0),))
    assert controller.evaluate((_value(7.0, row=1),))[0].is_active

    controller.set_rules((Wits0SavedAlarmRule(mnemonic="TOTAL_GAS", maximum=10.0),))
    status = controller.evaluate((_value(7.0, row=1),))

    assert not status[0].is_active
