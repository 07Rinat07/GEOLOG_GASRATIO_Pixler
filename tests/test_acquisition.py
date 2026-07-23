from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.domain.acquisition import (
    AcquisitionCurveSchema,
    AcquisitionDataRowPayload,
    AcquisitionDatasetSchema,
    AcquisitionEventDeletePayload,
    AcquisitionEventUpsertPayload,
    AcquisitionIndexSchema,
    AcquisitionRecord,
    AcquisitionRecordKind,
    AcquisitionSession,
    AcquisitionSessionState,
)
from geoworkbench.domain.models import (
    CurveMetadata,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    Well,
)
from geoworkbench.domain.operational_events import (
    GasEventPayload,
    OperationalEvent,
    OperationalEventKind,
    OperationalEventQcFlag,
    ShowEventPayload,
)
from geoworkbench.services.acquisition import (
    AcquisitionBackpressureError,
    AcquisitionConflictError,
    AcquisitionController,
    AcquisitionReplayError,
    acquisition_projection_digests,
    replay_acquisition_session,
)
from geoworkbench.services.operational_event_report import resolve_operational_event_report
from geoworkbench.services.report_definition import (
    ReportDefinition,
    ReportIntervalMode,
    ReportIntervalSelection,
    ReportProfile,
    ReportSectionDefinition,
    ReportSectionKind,
    resolve_report_definition,
)


def make_schema() -> AcquisitionDatasetSchema:
    return AcquisitionDatasetSchema(
        dataset_id="live-dataset",
        name="Live acquisition",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        indexes=(
            AcquisitionIndexSchema(
                index_id="depth-index",
                mnemonic="DEPT",
                index_type=IndexType.MD,
                role=IndexRole.DEPTH,
                unit="m",
            ),
        ),
        active_index_id="depth-index",
        curves=(
            AcquisitionCurveSchema(
                CurveMetadata(
                    curve_id="total-gas",
                    original_mnemonic="TG",
                    canonical_mnemonic="TG",
                    unit="%",
                    description="Total gas",
                    source_dataset_id="live-dataset",
                    provenance="acquisition",
                )
            ),
            AcquisitionCurveSchema(
                CurveMetadata(
                    curve_id="rop",
                    original_mnemonic="ROP",
                    canonical_mnemonic="ROP",
                    unit="m/h",
                    description="Rate of penetration",
                    source_dataset_id="live-dataset",
                    provenance="acquisition",
                )
            ),
        ),
    )


def row_record(sequence: int, depth: float, gas: float | None, rop: float) -> AcquisitionRecord:
    return AcquisitionRecord(
        record_id=f"row-{sequence}",
        sequence=sequence,
        kind=AcquisitionRecordKind.DATA_ROW,
        payload=AcquisitionDataRowPayload(
            index_values=(("depth-index", depth),),
            curve_values=(("total-gas", gas), ("rop", rop)),
        ),
        received_at=f"2026-07-23T10:0{sequence}:00+05:00",
        source="fixture:recording",
    )


def gas_event(event_id: str, depth: float, received_minute: int) -> OperationalEvent:
    return OperationalEvent(
        event_id=event_id,
        well_id="well-1",
        kind=OperationalEventKind.GAS,
        payload=GasEventPayload(total_gas_percent=1.5),
        depth_m=depth,
        measured_at="2026-07-23T10:00:00+05:00",
        received_at=f"2026-07-23T10:{received_minute:02d}:00+05:00",
        source="sensor:gas",
    )


def event_record(sequence: int, event: OperationalEvent) -> AcquisitionRecord:
    return AcquisitionRecord(
        record_id=f"event-{sequence}",
        sequence=sequence,
        kind=AcquisitionRecordKind.EVENT_UPSERT,
        payload=AcquisitionEventUpsertPayload(event),
        received_at=event.received_at or "2026-07-23T05:00:00Z",
        source="fixture:recording",
    )


def test_append_only_dataset_buffer_checkpoint_and_controlled_close() -> None:
    well = Well("well-1", "Well 1")
    session = AcquisitionSession("session-1", well.well_id, make_schema())
    controller = AcquisitionController(well, session, max_pending_records=2)

    controller.enqueue(row_record(1, 100.0, 1.0, 12.0))
    controller.enqueue(row_record(2, 101.0, None, 10.0))
    with pytest.raises(AcquisitionBackpressureError, match="buffer"):
        controller.enqueue(row_record(3, 102.0, 2.0, 8.0))

    results = controller.drain()
    assert [item.sequence for item in results] == [1, 2]
    assert controller.pending_count == 0
    assert controller.dataset.depth.tolist() == [100.0, 101.0]
    assert controller.dataset.curves["total-gas"].values[0] == 1.0
    assert np.isnan(controller.dataset.curves["total-gas"].values[1])
    assert session.records == [row_record(1, 100.0, 1.0, 12.0), row_record(2, 101.0, None, 10.0)]

    checkpoint = controller.create_checkpoint(
        "checkpoint-2", created_at="2026-07-23T10:02:30+05:00"
    )
    controller.verify_checkpoint(checkpoint)
    final = controller.close(
        checkpoint_id="checkpoint-final",
        closed_at="2026-07-23T10:03:00+05:00",
    )

    assert session.state is AcquisitionSessionState.CLOSED
    assert session.final_audit_digest == final.audit_digest
    with pytest.raises(AcquisitionConflictError, match="закрыта"):
        controller.append(row_record(3, 102.0, 2.0, 8.0))


def test_sequence_schema_and_checkpoint_conflicts_do_not_mutate_projection() -> None:
    well = Well("well-1", "Well 1")
    session = AcquisitionSession("session-1", well.well_id, make_schema())
    controller = AcquisitionController(well, session)

    with pytest.raises(AcquisitionConflictError, match="sequence conflict"):
        controller.append(row_record(2, 100.0, 1.0, 12.0))
    assert len(controller.dataset.depth) == 0
    assert session.records == []

    wrong_schema_record = AcquisitionRecord(
        record_id="wrong",
        sequence=1,
        kind=AcquisitionRecordKind.DATA_ROW,
        payload=AcquisitionDataRowPayload(
            index_values=(("depth-index", 100.0),),
            curve_values=(("total-gas", 1.0),),
        ),
        received_at="2026-07-23T10:00:00+05:00",
        source="fixture",
    )
    with pytest.raises(AcquisitionConflictError, match="точный набор acquisition curves"):
        controller.append(wrong_schema_record)

    controller.append(row_record(1, 100.0, 1.0, 12.0))
    checkpoint = controller.create_checkpoint(
        "checkpoint-1", created_at="2026-07-23T10:01:00+05:00"
    )
    controller.dataset.curves["rop"].values[0] = 999.0
    with pytest.raises(AcquisitionConflictError, match="fingerprint|append-only source"):
        controller.verify_checkpoint(checkpoint)


def test_recorded_replay_recreates_dataset_events_qc_and_report() -> None:
    source_well = Well("well-1", "Well 1")
    session = AcquisitionSession("session-1", source_well.well_id, make_schema())
    controller = AcquisitionController(source_well, session)
    controller.append(row_record(1, 100.0, 1.0, 12.0))
    controller.append(row_record(2, 140.0, 2.0, 8.0))
    controller.append(event_record(3, gas_event("gas-late", 140.0, 1)))
    controller.append(event_record(4, gas_event("gas-early", 100.0, 2)))
    controller.create_checkpoint(
        "checkpoint-4", created_at="2026-07-23T10:04:00+05:00"
    )
    controller.append(
        AcquisitionRecord(
            record_id="show-5",
            sequence=5,
            kind=AcquisitionRecordKind.EVENT_UPSERT,
            payload=AcquisitionEventUpsertPayload(
                OperationalEvent(
                    event_id="show-1",
                    well_id="well-1",
                    kind=OperationalEventKind.SHOW,
                    payload=ShowEventPayload("oil", intensity=3),
                    depth_m=105.0,
                    received_at="2026-07-23T10:03:00+05:00",
                    source="geologist",
                )
            ),
            received_at="2026-07-23T10:03:00+05:00",
            source="fixture:recording",
        )
    )
    controller.close(
        checkpoint_id="checkpoint-final",
        closed_at="2026-07-23T10:05:00+05:00",
    )

    assert (
        OperationalEventQcFlag.OUT_OF_ORDER
        in source_well.operational_events["gas-early"].qc_flags
    )
    assert OperationalEventQcFlag.GAP in source_well.operational_events["gas-late"].qc_flags

    target_well = Well("well-1", "Replay well")
    replay = replay_acquisition_session(session, target_well)

    assert replay.records_replayed == 5
    assert target_well.operational_events == source_well.operational_events
    assert target_well.datasets["live-dataset"].depth.tolist() == [100.0, 140.0]
    assert acquisition_projection_digests(
        target_well.datasets["live-dataset"], target_well
    ) == acquisition_projection_digests(
        source_well.datasets["live-dataset"], source_well
    )

    definition = ReportDefinition(
        definition_id="events-report",
        name="Events",
        profile=ReportProfile.EVENTS,
        dataset_id="live-dataset",
        index_id="depth-index",
        interval=ReportIntervalSelection(ReportIntervalMode.CUSTOM, 100.0, 140.0),
        sections=(ReportSectionDefinition(ReportSectionKind.EVENTS),),
    )
    source_resolved = resolve_report_definition(source_well.datasets["live-dataset"], definition)
    target_resolved = resolve_report_definition(target_well.datasets["live-dataset"], definition)
    source_report = resolve_operational_event_report(
        source_well, source_well.datasets["live-dataset"], source_resolved
    )
    target_report = resolve_operational_event_report(
        target_well, target_well.datasets["live-dataset"], target_resolved
    )
    assert target_report == source_report


def test_event_update_delete_and_checkpoint_resume_are_deterministic() -> None:
    source_well = Well("well-1", "Well 1")
    session = AcquisitionSession("session-1", source_well.well_id, make_schema())
    controller = AcquisitionController(source_well, session)
    controller.append(row_record(1, 100.0, 1.0, 12.0))
    initial = gas_event("gas-1", 100.0, 1)
    controller.append(event_record(2, initial))
    checkpoint = controller.create_checkpoint(
        "checkpoint-2", created_at="2026-07-23T10:02:00+05:00"
    )
    replacement = replace(initial, depth_m=101.0, revision=2)
    controller.append(
        AcquisitionRecord(
            "event-update-3",
            3,
            AcquisitionRecordKind.EVENT_UPSERT,
            AcquisitionEventUpsertPayload(replacement, expected_revision=1),
            "2026-07-23T10:03:00+05:00",
            "fixture",
        )
    )
    controller.append(
        AcquisitionRecord(
            "event-delete-4",
            4,
            AcquisitionRecordKind.EVENT_DELETE,
            AcquisitionEventDeletePayload("gas-1", expected_revision=2),
            "2026-07-23T10:04:00+05:00",
            "fixture",
        )
    )

    target_well = Well("well-1", "Target")
    target_session = AcquisitionSession("session-1", target_well.well_id, make_schema())
    target_controller = AcquisitionController(target_well, target_session)
    for record in session.records[: checkpoint.sequence]:
        target_controller.append(record)
    target_session.checkpoints.append(checkpoint)

    result = replay_acquisition_session(
        session,
        target_well,
        checkpoint_id="checkpoint-2",
    )
    assert result.records_replayed == 2
    assert target_well.operational_events == {}
    assert target_session.records == session.records


def test_replay_rejects_tampered_checkpoint_projection() -> None:
    source_well = Well("well-1", "Well 1")
    session = AcquisitionSession("session-1", source_well.well_id, make_schema())
    controller = AcquisitionController(source_well, session)
    controller.append(row_record(1, 100.0, 1.0, 12.0))
    checkpoint = controller.create_checkpoint(
        "checkpoint-1", created_at="2026-07-23T10:01:00+05:00"
    )

    target_well = Well("well-1", "Target")
    target_session = AcquisitionSession("session-1", target_well.well_id, make_schema())
    target_controller = AcquisitionController(target_well, target_session)
    target_controller.append(session.records[0])
    target_session.checkpoints.append(checkpoint)
    target_controller.dataset.curves["rop"].values[0] = 999.0

    with pytest.raises(AcquisitionReplayError, match="fingerprint|append-only source"):
        replay_acquisition_session(
            session,
            target_well,
            checkpoint_id="checkpoint-1",
        )


def test_buffer_limits_require_real_integers() -> None:
    for invalid in (True, 0, 1.5):
        well = Well("well-1", "Well 1")
        session = AcquisitionSession("session-1", well.well_id, make_schema())
        with pytest.raises(ValueError, match="положительным целым"):
            AcquisitionController(
                well,
                session,
                max_pending_records=invalid,  # type: ignore[arg-type]
            )
        assert well.datasets == {}
        assert well.acquisition_sessions == {}

    well = Well("well-1", "Well 1")
    session = AcquisitionSession("session-1", well.well_id, make_schema())
    controller = AcquisitionController(well, session)
    with pytest.raises(ValueError, match="неотрицательным целым"):
        controller.drain(limit=1.5)  # type: ignore[arg-type]


def test_resume_replay_is_transactional_when_later_record_diverges() -> None:
    source_well = Well("well-1", "Source")
    source_session = AcquisitionSession("session-1", source_well.well_id, make_schema())
    source_controller = AcquisitionController(source_well, source_session)
    source_controller.append(row_record(1, 100.0, 1.0, 12.0))
    checkpoint = source_controller.create_checkpoint(
        "checkpoint-1", created_at="2026-07-23T10:01:00+05:00"
    )
    source_controller.append(row_record(2, 101.0, 2.0, 10.0))
    source_session.records.append(
        AcquisitionRecord(
            "invalid-delete-3",
            3,
            AcquisitionRecordKind.EVENT_DELETE,
            AcquisitionEventDeletePayload("missing-event", expected_revision=1),
            "2026-07-23T10:03:00+05:00",
            "fixture",
        )
    )

    target_well = Well("well-1", "Target")
    target_session = AcquisitionSession("session-1", target_well.well_id, make_schema())
    target_controller = AcquisitionController(target_well, target_session)
    target_controller.append(source_session.records[0])
    target_session.checkpoints.append(checkpoint)
    before_records = list(target_session.records)
    before_depth = target_controller.dataset.depth.copy()
    before_digests = acquisition_projection_digests(target_controller.dataset, target_well)

    with pytest.raises(AcquisitionReplayError, match="sequence 3"):
        replay_acquisition_session(
            source_session,
            target_well,
            checkpoint_id="checkpoint-1",
        )

    assert target_session.records == before_records
    assert np.array_equal(target_controller.dataset.depth, before_depth)
    assert acquisition_projection_digests(target_controller.dataset, target_well) == before_digests
    assert target_well.operational_events == {}


def test_controller_rejects_diverged_historical_checkpoint_on_restore() -> None:
    well = Well("well-1", "Well 1")
    session = AcquisitionSession("session-1", well.well_id, make_schema())
    controller = AcquisitionController(well, session)
    controller.append(row_record(1, 100.0, 1.0, 12.0))
    checkpoint = controller.create_checkpoint(
        "checkpoint-1", created_at="2026-07-23T10:01:00+05:00"
    )
    controller.append(row_record(2, 101.0, 2.0, 10.0))
    session.checkpoints[0] = replace(checkpoint, dataset_digest="0" * 64)

    with pytest.raises(AcquisitionConflictError, match="checkpoint diverged"):
        AcquisitionController(well, session)
