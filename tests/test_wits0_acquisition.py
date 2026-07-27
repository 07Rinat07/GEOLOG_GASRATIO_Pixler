from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import numpy as np
import pytest

from geoworkbench.acquisition import (
    Wits0SequenceStatus,
    Wits0StreamProcessor,
    iter_parsed_wits0_frames,
    load_builtin_wits0_profile,
    process_wits0_chunks,
)
from geoworkbench.domain.acquisition import AcquisitionSessionState
from geoworkbench.domain.models import IndexType, Well
from geoworkbench.services.acquisition import AcquisitionBackpressureError, AcquisitionController
from geoworkbench.services.wits0_acquisition import (
    Wits0AcquisitionBackpressureError,
    Wits0AcquisitionConfig,
    Wits0AcquisitionRuntime,
    Wits0AcquisitionState,
    Wits0BackpressurePolicy,
    Wits0FrameNormalizer,
    Wits0NormalizationCode,
)
from geoworkbench.services.wits0_import_review import (
    Wits0DiscoveryAccumulator,
    Wits0ImportReviewController,
)


def _frame(record: int, sequence: int, *lines: str) -> bytes:
    return "\r\n".join(
        (
            "&&",
            f"{record:02d}01{record:02d}",
            f"{record:02d}02{sequence}",
            f"{record:02d}05260727",
            f"{record:02d}060315450",
            f"{record:02d}070",
            *lines,
            "!!",
        )
    ).encode("ascii")


def _time_commit(*raw_frames: bytes):  # type: ignore[no-untyped-def]
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    frames = []
    for raw in raw_frames:
        frames.extend(
            processor.append(
                raw,
                received_at="2026-07-27T03:15:45Z",
                source_ref="fixture.wits",
            )
        )
    accumulator = Wits0DiscoveryAccumulator(profile)
    accumulator.observe_many(frames)
    snapshot = accumulator.snapshot()
    review = Wits0ImportReviewController()
    commit = review.commit(snapshot, profile, review.initial_plan(snapshot))
    return profile, tuple(frames), commit


def _depth_commit(*raw_frames: bytes):  # type: ignore[no-untyped-def]
    profile, frames, time_commit = _time_commit(*raw_frames)
    accumulator = Wits0DiscoveryAccumulator(profile)
    accumulator.observe_many(frames)
    snapshot = accumulator.snapshot()
    review = Wits0ImportReviewController()
    plan = review.initial_plan(snapshot)
    depth = next(
        item for item in review.index_candidates(snapshot) if item.candidate_id == "field:0208"
    )
    plan = replace(
        plan,
        index_candidate_id=depth.candidate_id,
        index_mnemonic="MD",
        index_type=IndexType.MD,
        index_unit="m",
        timezone=None,
    )
    return profile, frames, review.commit(snapshot, profile, plan)


def test_time_normalizer_creates_complete_measurement_batch() -> None:
    _profile, frames, commit = _time_commit(
        _frame(2, 1, "0208123.4", "021011.2", "029912.5")
    )

    result = Wits0FrameNormalizer(commit).normalize(frames[0])

    assert result.accepted and result.batch is not None
    batch = result.batch
    assert batch.record_no == 2
    assert batch.source_sequence_no == 1
    assert batch.sequence_status is Wits0SequenceStatus.FIRST
    assert batch.received_at == "2026-07-27T03:15:45.000000Z"
    assert len(batch.index_values) == 1
    index_value = batch.index_values[0][1]
    assert isinstance(index_value, int)
    values = {item.source_id: item.value for item in batch.measurements}
    assert values == {"0208": 123.4, "0210": 11.2, "0299": 12.5}
    assert batch.non_null_count == 3
    assert len(batch.batch_id) == 64


def test_depth_normalizer_omits_index_curve_and_fills_missing_values_with_none() -> None:
    _profile, frames, commit = _depth_commit(
        _frame(2, 1, "0208123.4", "021011.2", "029912.5"),
        _frame(2, 2, "0208123.6", "021012.0"),
    )
    normalizer = Wits0FrameNormalizer(commit)

    result = normalizer.normalize(frames[1])

    assert result.batch is not None
    batch = result.batch
    assert batch.index_values[0][1] == 123.6
    values = {item.source_id: item.value for item in batch.measurements}
    assert "0208" not in values
    assert values["0210"] == 12.0
    assert values["0299"] is None
    assert any(
        item.code is Wits0NormalizationCode.MISSING_CURVE_VALUE
        for item in batch.diagnostics
    )


def test_duplicate_and_out_of_order_source_sequences_are_skipped() -> None:
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    frames = []
    for sequence in (10, 10, 8):
        frames.extend(
            processor.append(
                _frame(2, sequence, "0208123.4", "021011.2"),
                received_at="2026-07-27T03:15:45Z",
            )
        )
    accumulator = Wits0DiscoveryAccumulator(profile)
    accumulator.observe_many(frames)
    snapshot = accumulator.snapshot()
    review = Wits0ImportReviewController()
    commit = review.commit(snapshot, profile, review.initial_plan(snapshot))
    normalizer = Wits0FrameNormalizer(commit)

    first, duplicate, out_of_order = (normalizer.normalize(item) for item in frames)

    assert first.batch is not None
    assert duplicate.batch is None
    assert duplicate.diagnostics[0].code is Wits0NormalizationCode.DUPLICATE_SEQUENCE_SKIPPED
    assert out_of_order.batch is None
    assert (
        out_of_order.diagnostics[0].code
        is Wits0NormalizationCode.OUT_OF_ORDER_SEQUENCE_SKIPPED
    )


def test_live_and_replay_create_identical_normalized_batches() -> None:
    profile = load_builtin_wits0_profile()
    raw = _frame(2, 1, "0208123.4", "021011.2") + _frame(
        2, 2, "0208123.6", "021012.0"
    )
    live = process_wits0_chunks(
        (raw[:4], raw[4:39], raw[39:91], raw[91:]),
        profile=profile,
        received_at="2026-07-27T03:15:45Z",
        source_ref="same.wits",
    )
    replay = tuple(
        iter_parsed_wits0_frames(
            BytesIO(raw),
            profile=profile,
            chunk_size=7,
            received_at="2026-07-27T03:15:45Z",
            source_ref="same.wits",
        )
    )
    accumulator = Wits0DiscoveryAccumulator(profile)
    accumulator.observe_many(live)
    snapshot = accumulator.snapshot()
    review = Wits0ImportReviewController()
    commit = review.commit(snapshot, profile, review.initial_plan(snapshot))
    normalizer = Wits0FrameNormalizer(commit)

    live_batches = tuple(normalizer.normalize(item).batch for item in live)
    replay_batches = tuple(normalizer.normalize(item).batch for item in replay)

    assert live_batches == replay_batches


def test_acquisition_controller_enqueue_many_is_atomic_under_capacity_failure() -> None:
    _profile, frames, commit = _time_commit(
        _frame(2, 1, "0208123.4", "021011.2"),
        _frame(2, 2, "0208123.6", "021012.0"),
    )
    normalizer = Wits0FrameNormalizer(commit)
    batches = tuple(normalizer.normalize(item).batch for item in frames)
    assert all(item is not None for item in batches)
    well = Well("well-1", "Well 1")
    runtime = Wits0AcquisitionRuntime(
        well,
        commit,
        session_id="session-1",
        config=Wits0AcquisitionConfig(max_pending_records=1),
    )
    records = tuple(
        item.to_acquisition_record(index + 1)  # type: ignore[union-attr]
        for index, item in enumerate(batches)
    )

    with pytest.raises(AcquisitionBackpressureError):
        runtime.controller.enqueue_many(records)

    assert runtime.controller.pending_count == 0
    assert runtime.session.records == []
    assert len(runtime.controller.dataset.depth) == 0


def test_runtime_bounded_queue_backpressure_drain_checkpoint_and_controlled_close() -> None:
    _profile, frames, commit = _time_commit(
        _frame(2, 1, "0208123.4", "021011.2"),
        _frame(2, 2, "0208123.6", "021012.0"),
        _frame(2, 3, "0208123.8", "021013.0"),
    )
    clock = iter((0.0, 0.0, 0.0, 61.0, 61.0, 61.0, 61.0))
    well = Well("well-1", "Well 1")
    runtime = Wits0AcquisitionRuntime(
        well,
        commit,
        session_id="session-1",
        config=Wits0AcquisitionConfig(
            max_pending_records=2,
            drain_batch_size=1,
            checkpoint_every_records=2,
            checkpoint_interval_seconds=60.0,
            backpressure_policy=Wits0BackpressurePolicy.RAISE,
        ),
        monotonic=lambda: next(clock),
    )

    runtime.submit_frame(frames[0])
    runtime.submit_frame(frames[1])
    with pytest.raises(Wits0AcquisitionBackpressureError):
        runtime.submit_frame(frames[2])
    assert runtime.snapshot().pending_records == 2
    assert runtime.snapshot().backpressure_count == 1

    applied = runtime.drain()
    assert [item.sequence for item in applied] == [1, 2]
    assert runtime.last_checkpoint_sequence == 2
    runtime.submit_frame(frames[2])
    assert runtime.flush()[0].sequence == 3

    final = runtime.close(closed_at="2026-07-27T03:20:00Z")

    assert final.sequence == 3
    assert runtime.state is Wits0AcquisitionState.CLOSED
    assert runtime.session.state is AcquisitionSessionState.CLOSED
    assert runtime.session.final_audit_digest == final.audit_digest
    assert well.datasets[commit.schema.dataset_id].depth.tolist() == [0.0, 1.0, 2.0]
    curve_values = next(iter(well.datasets[commit.schema.dataset_id].curves.values())).values
    assert len(curve_values) == 3
    assert runtime.snapshot().pending_records == 0
    with pytest.raises(Exception, match="not open"):
        runtime.submit_frame(frames[0])


def test_drain_then_retry_policy_relives_backpressure_without_losing_order() -> None:
    _profile, frames, commit = _time_commit(
        _frame(2, 1, "0208123.4", "021011.2"),
        _frame(2, 2, "0208123.6", "021012.0"),
    )
    well = Well("well-1", "Well 1")
    runtime = Wits0AcquisitionRuntime(
        well,
        commit,
        session_id="session-1",
        config=Wits0AcquisitionConfig(
            max_pending_records=1,
            drain_batch_size=1,
            checkpoint_every_records=100,
            checkpoint_interval_seconds=3600,
            backpressure_policy=Wits0BackpressurePolicy.DRAIN_THEN_RETRY,
        ),
    )

    runtime.submit_frame(frames[0])
    runtime.submit_frame(frames[1])

    assert runtime.session.last_sequence == 1
    assert runtime.controller.pending_count == 1
    runtime.close(closed_at="2026-07-27T03:20:00Z")
    assert runtime.session.last_sequence == 2
    assert runtime.snapshot().backpressure_count == 1
    assert np.asarray(runtime.controller.dataset.active_index.values).shape == (2,)


def test_closed_wits0_session_roundtrips_through_project_codec(tmp_path) -> None:
    from geoworkbench.domain.models import Project
    from geoworkbench.storage.atomic_json import save_project
    from geoworkbench.storage.project_codec import load_project

    _profile, frames, commit = _time_commit(
        _frame(2, 1, "0208123.4", "021011.2")
    )
    well = Well("well-1", "Well 1")
    runtime = Wits0AcquisitionRuntime(well, commit, session_id="session-1")
    runtime.submit_frame(frames[0])
    runtime.close(closed_at="2026-07-27T03:20:00Z")
    project = Project("project-1", "Project", wells={well.well_id: well})
    target = tmp_path / "wits0-project.json"

    save_project(project, target)
    loaded = load_project(target)

    loaded_well = loaded.wells[well.well_id]
    loaded_session = loaded_well.acquisition_sessions["session-1"]
    assert loaded_session == runtime.session
    assert loaded_well.datasets[commit.schema.dataset_id].active_index.values.tolist() == (
        runtime.controller.dataset.active_index.values.tolist()
    )


def test_open_session_can_resume_after_project_reload_without_sequence_reset(tmp_path) -> None:
    from geoworkbench.domain.models import Project
    from geoworkbench.storage.atomic_json import save_project
    from geoworkbench.storage.project_codec import load_project

    _profile, frames, commit = _time_commit(
        _frame(2, 1, "0208123.4", "021011.2"),
        _frame(2, 2, "0208123.6", "021012.0"),
    )
    well = Well("well-1", "Well 1")
    runtime = Wits0AcquisitionRuntime(well, commit, session_id="session-1")
    runtime.submit_frame(frames[0])
    runtime.flush()
    runtime.create_checkpoint(created_at="2026-07-27T03:16:00Z", force=True)

    target = tmp_path / "open-session.json"
    save_project(Project("project-1", "Project", wells={well.well_id: well}), target)
    loaded = load_project(target)
    loaded_well = loaded.wells[well.well_id]
    loaded_session = loaded_well.acquisition_sessions["session-1"]

    resumed = Wits0AcquisitionRuntime(
        loaded_well,
        commit,
        session_id="session-1",
        session=loaded_session,
    )
    initial = resumed.snapshot()
    assert initial.records_applied == 1
    assert initial.records_enqueued == 1
    assert initial.queue_capacity == resumed.config.max_pending_records
    assert initial.queue_remaining_capacity == resumed.config.max_pending_records

    resumed.submit_frame(frames[1])
    resumed.close(closed_at="2026-07-27T03:20:00Z")

    assert [item.sequence for item in resumed.session.records] == [1, 2]
    assert resumed.controller.dataset.active_index.values.shape == (2,)
    assert resumed.snapshot().records_applied == 2
