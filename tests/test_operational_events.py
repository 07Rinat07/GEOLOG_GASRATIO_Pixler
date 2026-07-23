from dataclasses import replace

import pytest

from geoworkbench.domain.models import Well
from geoworkbench.domain.operational_events import (
    CasingEventPayload,
    DrillingEventPayload,
    FormationTopEventPayload,
    GasEventPayload,
    OperationalEvent,
    OperationalEventKind,
    OperationalEventQcFlag,
    SampleEventPayload,
    ShowEventPayload,
)
from geoworkbench.services.operational_event_controller import (
    OperationalEventConflictError,
    OperationalEventController,
)
from geoworkbench.services.operational_event_qc import (
    OperationalEventQcEvaluator,
    OperationalEventQcPolicy,
)


def gas_event(
    event_id: str,
    depth_m: float,
    *,
    measured_at: str = "2026-07-23T10:00:00+05:00",
    received_at: str = "2026-07-23T10:00:30+05:00",
    calibration_id: str | None = "cal-1",
    calibrated_at: str | None = "2026-07-23T09:00:00+05:00",
    total_gas_percent: float = 1.0,
) -> OperationalEvent:
    return OperationalEvent(
        event_id=event_id,
        well_id="well-1",
        kind=OperationalEventKind.GAS,
        payload=GasEventPayload(total_gas_percent=total_gas_percent),
        depth_m=depth_m,
        measured_at=measured_at,
        received_at=received_at,
        source="sensor:gas-1",
        calibration_id=calibration_id,
        calibrated_at=calibrated_at,
    )


def test_all_typed_payloads_validate_against_event_kind() -> None:
    payloads = {
        OperationalEventKind.DRILLING: DrillingEventPayload(activity="drilling", rop_m_per_h=12.0),
        OperationalEventKind.GAS: GasEventPayload(total_gas_percent=1.2),
        OperationalEventKind.SHOW: ShowEventPayload("oil", intensity=3),
        OperationalEventKind.SAMPLE: SampleEventPayload("S-1", bottom_depth_m=1004.0),
        OperationalEventKind.CASING: CasingEventPayload("production", 177.8, shoe_depth_m=950.0),
        OperationalEventKind.FORMATION_TOP: FormationTopEventPayload("K1a", "Albian", 0.9),
    }

    for index, (kind, payload) in enumerate(payloads.items()):
        event = OperationalEvent(
            event_id=f"event-{index}",
            well_id="well-1",
            kind=kind,
            payload=payload,
            depth_m=1000.0 + index,
        )
        assert event.kind is kind

    with pytest.raises(ValueError, match="не соответствует"):
        OperationalEvent(
            event_id="wrong",
            well_id="well-1",
            kind=OperationalEventKind.GAS,
            payload=ShowEventPayload("oil"),
            depth_m=1000.0,
        )


def test_event_requires_anchor_and_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="требует depth_m"):
        OperationalEvent(
            event_id="event-1",
            well_id="well-1",
            kind=OperationalEventKind.SHOW,
            payload=ShowEventPayload("oil"),
        )

    with pytest.raises(ValueError, match="часовым поясом"):
        OperationalEvent(
            event_id="event-1",
            well_id="well-1",
            kind=OperationalEventKind.SHOW,
            payload=ShowEventPayload("oil"),
            measured_at="2026-07-23T10:00:00",
        )

    event = OperationalEvent(
        event_id="event-1",
        well_id="well-1",
        kind=OperationalEventKind.SHOW,
        payload=ShowEventPayload("oil"),
        measured_at="2026-07-23T10:00:00+05:00",
    )
    assert event.measured_at == "2026-07-23T05:00:00.000000Z"


def test_qc_marks_duplicate_order_gap_stale_and_calibration() -> None:
    evaluator = OperationalEventQcEvaluator(
        OperationalEventQcPolicy(
            max_depth_gap_m=5.0,
            max_time_gap_s=60.0,
            stale_after_s=60.0,
            calibration_ttl_s=1_800.0,
        )
    )
    events = [
        gas_event(
            "event-1",
            110.0,
            measured_at="2026-07-23T10:00:00+05:00",
            received_at="2026-07-23T10:00:30+05:00",
            calibrated_at="2026-07-23T09:00:00+05:00",
        ),
        gas_event(
            "event-2",
            100.0,
            measured_at="2026-07-23T10:01:00+05:00",
            received_at="2026-07-23T10:03:30+05:00",
            calibration_id=None,
            calibrated_at=None,
        ),
        gas_event(
            "event-3",
            110.0,
            measured_at="2026-07-23T10:00:00+05:00",
            received_at="2026-07-23T10:04:00+05:00",
            calibrated_at="2026-07-23T09:00:00+05:00",
        ),
    ]

    flags = evaluator.evaluate(events)

    assert OperationalEventQcFlag.DUPLICATE in flags["event-1"]
    assert OperationalEventQcFlag.DUPLICATE in flags["event-3"]
    assert OperationalEventQcFlag.OUT_OF_ORDER in flags["event-2"]
    assert OperationalEventQcFlag.GAP in flags["event-1"]
    assert OperationalEventQcFlag.STALE in flags["event-2"]
    assert OperationalEventQcFlag.CALIBRATION_MISSING in flags["event-2"]
    assert OperationalEventQcFlag.CALIBRATION_EXPIRED in flags["event-1"]


def test_controller_is_single_revisioned_mutation_boundary() -> None:
    well = Well("well-1", "Well 1")
    controller = OperationalEventController(well)
    created = controller.create(gas_event("event-1", 100.0))

    assert created.revision == 1
    assert controller.list_events() == (created,)

    replacement = replace(created, depth_m=101.0)
    updated = controller.update("event-1", replacement, expected_revision=1)
    assert updated.revision == 2
    assert updated.depth_m == 101.0

    with pytest.raises(OperationalEventConflictError, match="Revision conflict"):
        controller.update("event-1", replacement, expected_revision=1)

    removed = controller.remove("event-1", expected_revision=2)
    assert removed.event_id == "event-1"
    assert controller.list_events() == ()


def test_controller_rejects_cross_well_and_duplicate_ids() -> None:
    well = Well("well-1", "Well 1")
    controller = OperationalEventController(well)
    controller.create(gas_event("event-1", 100.0))

    with pytest.raises(OperationalEventConflictError, match="уже существует"):
        controller.create(gas_event("event-1", 101.0))

    foreign = replace(gas_event("event-2", 101.0), well_id="well-2")
    with pytest.raises(OperationalEventConflictError, match="другой скважине"):
        controller.create(foreign)
