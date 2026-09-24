from __future__ import annotations

import pytest

from geoworkbench.acquisition import Wits0StreamProcessor, load_builtin_wits0_profile
from geoworkbench.domain.models import Well
from geoworkbench.services.wits0_acquisition import Wits0AcquisitionRuntime
from geoworkbench.services.wits0_import_review import Wits0ImportReviewController
from geoworkbench.services.wits0_live_preview import (
    Wits0LivePreview,
    Wits0LivePreviewConfig,
    Wits0PreviewHistoryTruncatedError,
)


def _frame(record: int, sequence: int, *lines: str) -> bytes:
    return "\r\n".join(
        (
            "&&",
            f"{record:02d}01СКВАЖИНА-8",
            f"{record:02d}0201",
            f"{record:02d}03{record}",
            f"{record:02d}04{sequence}",
            f"{record:02d}05260727",
            f"{record:02d}060315450",
            f"{record:02d}070",
            *lines,
            "!!",
        )
    ).encode("cp1251")


def _frame_without_datetime(record: int, sequence: int, *lines: str) -> bytes:
    return "\r\n".join(
        (
            "&&",
            f"{record:02d}01СКВАЖИНА-8",
            f"{record:02d}0201",
            f"{record:02d}03{record}",
            f"{record:02d}04{sequence}",
            f"{record:02d}070",
            *lines,
            "!!",
        )
    ).encode("cp1251")


def _parsed_frames(*raw_frames: bytes):  # type: ignore[no-untyped-def]
    processor = Wits0StreamProcessor(load_builtin_wits0_profile())
    frames = []
    for raw in raw_frames:
        frames.extend(
            processor.append(
                raw,
                received_at="2026-07-27T03:15:45Z",
                source_ref="live-preview.wits",
            )
        )
    return tuple(frames)


def test_preview_renders_frames_without_project_well_or_review_commit() -> None:
    profile = load_builtin_wits0_profile()
    first, second = _parsed_frames(
        _frame(2, 1, "0208123.4", "021011.2"),
        _frame(2, 2, "0208123.6", "021012.0"),
    )
    preview = Wits0LivePreview(profile)

    first_runtime = preview.observe(first)
    second_runtime = preview.observe(second)

    assert first_runtime is not None
    assert second_runtime is first_runtime
    assert preview.buffered_frame_count == 2
    assert preview.last_error is None
    assert second_runtime.controller.dataset.active_index.values.shape == (2,)
    assert second_runtime.controller.dataset.curves


def test_preview_uses_received_at_when_later_frame_omits_wits_datetime() -> None:
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    first = processor.append(
        _frame(2, 1, "0208123.4", "021011.2"),
        received_at="2026-07-27T03:15:45Z",
        source_ref="live-preview.wits",
    )[0]
    second = processor.append(
        _frame_without_datetime(2, 2, "0208123.6", "021012.0"),
        received_at="2026-07-27T03:15:46Z",
        source_ref="live-preview.wits",
    )[0]
    preview = Wits0LivePreview(profile)

    first_runtime = preview.observe(first)
    second_runtime = preview.observe(second)

    assert first_runtime is not None
    assert second_runtime is first_runtime
    assert preview.last_error is None
    assert preview.buffered_frame_count == 2
    assert second_runtime.snapshot().frames_skipped == 0
    active = second_runtime.controller.dataset.active_index.values
    assert active.shape == (2,)
    assert active[1] > active[0]


def test_preview_rebuilds_when_new_channels_arrive_and_preserves_buffer() -> None:
    profile = load_builtin_wits0_profile()
    first, second = _parsed_frames(
        _frame(2, 1, "0208123.4", "021011.2"),
        _frame(2, 2, "0208123.6", "021012.0", "021319.5"),
    )
    preview = Wits0LivePreview(
        profile,
        config=Wits0LivePreviewConfig(max_buffered_frames=10),
    )

    first_runtime = preview.observe(first)
    second_runtime = preview.observe(second)

    assert first_runtime is not None
    assert second_runtime is not None
    assert second_runtime is not first_runtime
    assert second_runtime.controller.dataset.active_index.values.shape == (2,)
    assert any(
        curve.metadata.provenance == "wits0:0213"
        for curve in second_runtime.controller.dataset.curves.values()
    )


def test_preview_backfills_buffer_through_confirmed_persistent_schema() -> None:
    profile = load_builtin_wits0_profile()
    frames = _parsed_frames(
        _frame(2, 1, "0208123.4", "021011.2"),
        _frame(2, 2, "0208123.6", "021012.0"),
    )
    preview = Wits0LivePreview(profile)
    for frame in frames:
        preview.observe(frame)
    snapshot = preview.discovery.snapshot()
    reviewer = Wits0ImportReviewController()
    commit = reviewer.commit(snapshot, profile, reviewer.initial_plan(snapshot))
    well = Well("well-1", "Well 1")
    runtime = Wits0AcquisitionRuntime(well, commit, session_id="session-1")

    backfilled = preview.backfill(runtime)

    assert backfilled == 2
    assert runtime.controller.dataset.active_index.values.shape == (2,)
    assert runtime.session.last_sequence == 2
    assert well.datasets[commit.schema.dataset_id] is runtime.controller.dataset



def test_preview_backfill_fails_closed_after_history_eviction() -> None:
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    preview = Wits0LivePreview(
        profile,
        config=Wits0LivePreviewConfig(
            max_buffered_frames=2,
            runtime_compaction_factor=2,
        ),
    )

    for sequence in range(1, 4):
        frame = processor.append(
            _frame(2, sequence, f"0208{123.0 + sequence / 10:.1f}"),
            received_at=f"2026-07-27T03:18:{sequence:02d}Z",
            source_ref="truncated-preview.wits",
        )[0]
        preview.observe(frame)

    boundary = preview.backfill_boundary
    assert boundary.truncated is True
    assert boundary.evicted_frames == 1
    assert boundary.first_observed_received_at == "2026-07-27T03:18:01Z"
    assert boundary.buffered_frames == 2
    assert boundary.earliest_received_at == "2026-07-27T03:18:02Z"
    assert boundary.latest_received_at == "2026-07-27T03:18:03Z"

    snapshot = preview.discovery.snapshot()
    reviewer = Wits0ImportReviewController()
    commit = reviewer.commit(snapshot, profile, reviewer.initial_plan(snapshot))
    well = Well("well-guard", "Well guard")
    runtime = Wits0AcquisitionRuntime(well, commit, session_id="session-guard")

    with pytest.raises(Wits0PreviewHistoryTruncatedError, match="evicted=1"):
        preview.backfill(runtime)

    assert runtime.session.last_sequence == 0
    assert len(runtime.controller.dataset.active_index.values) == 0


def test_preview_retained_tail_requires_exact_explicit_boundary() -> None:
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    preview = Wits0LivePreview(
        profile,
        config=Wits0LivePreviewConfig(
            max_buffered_frames=2,
            runtime_compaction_factor=2,
        ),
    )

    for sequence in range(1, 4):
        frame = processor.append(
            _frame(2, sequence, f"0208{123.0 + sequence / 10:.1f}"),
            received_at=f"2026-07-27T03:19:{sequence:02d}Z",
            source_ref="truncated-preview.wits",
        )[0]
        preview.observe(frame)

    snapshot = preview.discovery.snapshot()
    reviewer = Wits0ImportReviewController()
    commit = reviewer.commit(snapshot, profile, reviewer.initial_plan(snapshot))
    well = Well("well-boundary", "Well boundary")
    runtime = Wits0AcquisitionRuntime(
        well,
        commit,
        session_id="session-boundary",
    )

    with pytest.raises(ValueError, match="must match"):
        preview.backfill_from_explicit_boundary(
            runtime,
            accepted_start_at="2026-07-27T03:19:01Z",
        )

    assert runtime.session.last_sequence == 0

    accepted = preview.backfill_from_explicit_boundary(
        runtime,
        accepted_start_at="2026-07-27T03:19:02Z",
    )

    assert accepted == 2
    assert runtime.session.last_sequence == 2
    assert runtime.session.records[0].received_at == "2026-07-27T03:19:02.000000Z"


def test_preview_runtime_history_is_bounded_beyond_ten_times_frame_limit() -> None:
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    config = Wits0LivePreviewConfig(
        max_buffered_frames=3,
        max_pending_records=16,
        drain_batch_size=4,
        runtime_compaction_factor=2,
    )
    preview = Wits0LivePreview(profile, config=config)
    first_curve_ids: set[str] | None = None

    for sequence in range(1, 31):
        parsed = processor.append(
            _frame(2, sequence, f"0208{123.0 + sequence / 10:.1f}", f"0210{sequence:.1f}"),
            received_at=f"2026-07-27T03:16:{sequence % 60:02d}Z",
            source_ref="bounded-preview.wits",
        )
        assert len(parsed) == 1
        runtime = preview.observe(parsed[0])
        assert runtime is not None
        if first_curve_ids is None:
            first_curve_ids = set(runtime.controller.dataset.curves)
        assert preview.buffered_frame_count <= config.max_buffered_frames
        assert preview.retained_row_count <= config.max_runtime_rows
        assert len(runtime.session.records) <= config.max_runtime_rows
        assert len(runtime.controller.dataset.active_index.values) <= config.max_runtime_rows
        assert all(
            len(curve.values) <= config.max_runtime_rows
            for curve in runtime.controller.dataset.curves.values()
        )

    runtime = preview.runtime
    assert runtime is not None
    assert preview.buffered_frame_count == config.max_buffered_frames
    assert preview.evicted_frame_count == 27
    assert preview.compaction_count > 0
    assert preview.history_is_truncated is True
    assert first_curve_ids == set(runtime.controller.dataset.curves)
    assert len(runtime.controller._known_record_ids) <= config.max_runtime_rows


def test_preview_reset_clears_retention_counters() -> None:
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    preview = Wits0LivePreview(
        profile,
        config=Wits0LivePreviewConfig(
            max_buffered_frames=2,
            runtime_compaction_factor=2,
        ),
    )

    for sequence in range(1, 7):
        frame = processor.append(
            _frame(2, sequence, f"0208{123.0 + sequence / 10:.1f}"),
            received_at=f"2026-07-27T03:17:{sequence:02d}Z",
            source_ref="bounded-preview.wits",
        )[0]
        preview.observe(frame)

    assert preview.evicted_frame_count > 0
    assert preview.history_is_truncated is True

    preview.reset()

    assert preview.buffered_frame_count == 0
    assert preview.retained_row_count == 0
    assert preview.evicted_frame_count == 0
    assert preview.compaction_count == 0
    assert preview.history_is_truncated is False
    assert preview.backfill_boundary.first_observed_received_at is None
