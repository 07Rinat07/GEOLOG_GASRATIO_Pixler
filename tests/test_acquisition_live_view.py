from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import numpy as np

from geoworkbench.acquisition import Wits0StreamProcessor, load_builtin_wits0_profile
from geoworkbench.domain.models import Well
from geoworkbench.services.acquisition_live_view import (
    AcquisitionLiveAxisMode,
    AcquisitionLiveMarkerKind,
    AcquisitionLiveQuality,
    AcquisitionLiveView,
    AcquisitionLiveViewConfig,
)
from geoworkbench.services.wits0_acquisition import Wits0AcquisitionRuntime
from geoworkbench.services.wits0_import_review import (
    Wits0DiscoveryAccumulator,
    Wits0ImportReviewController,
)


def _frame(
    sequence: int,
    *,
    time_value: str,
    depth: float,
    rop: float | None,
) -> bytes:
    lines = [
        "&&",
        "0201SG-8",
        "020201",
        "020302",
        f"0204{sequence}",
        "0205260727",
        f"0206{time_value}",
        "02070",
        f"0208{depth}",
    ]
    if rop is not None:
        lines.append(f"0210{rop}")
    lines.append("!!")
    return "\r\n".join(lines).encode("ascii")


def _runtime_with_frames(
    raw_frames: tuple[bytes, ...],
    *,
    index_candidate_id: str | None = None,
) -> tuple[Wits0AcquisitionRuntime, tuple]:
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    frames = []
    for offset, raw in enumerate(raw_frames):
        frames.extend(
            processor.append(
                raw,
                received_at=f"2026-07-27T03:15:{45 + min(offset, 14):02d}Z",
                source_ref="live.wits",
            )
        )
    discovery = Wits0DiscoveryAccumulator(profile)
    discovery.observe_many(frames)
    snapshot = discovery.snapshot()
    review = Wits0ImportReviewController()
    plan = review.initial_plan(snapshot)
    if index_candidate_id is not None:
        candidate = next(
            item
            for item in review.index_candidates(snapshot)
            if item.candidate_id == index_candidate_id
        )
        plan = replace(
            plan,
            index_id=f"index-{candidate.candidate_id.replace(':', '-')}",
            index_candidate_id=candidate.candidate_id,
            index_mnemonic=candidate.mnemonic,
            index_type=candidate.index_type,
            index_unit=candidate.canonical_uom,
            timezone="UTC" if candidate.source_kind == "header_datetime" else None,
        )
    commit = review.commit(snapshot, profile, plan)
    runtime = Wits0AcquisitionRuntime(Well("well-1", "Well 1"), commit, session_id="s-1")
    runtime.submit_frames(frames)
    runtime.flush()
    return runtime, tuple(frames)


def _curve_id(runtime: Wits0AcquisitionRuntime, source_id: str) -> str:
    for curve_id, curve in runtime.controller.dataset.curves.items():
        if curve.metadata.provenance == f"wits0:{source_id}":
            return curve_id
    raise AssertionError(f"Missing curve for {source_id}")


def test_record_source_persists_sequence_status_raw_hash_and_quality() -> None:
    runtime, _frames = _runtime_with_frames(
        (
            _frame(1, time_value="0315450", depth=100.0, rop=10.0),
            _frame(4, time_value="0316000", depth=101.0, rop=None),
        )
    )

    first, second = runtime.session.records

    assert "sequence-status=first" in first.source
    assert "raw-sha256=" in first.source
    assert "sequence-status=gap" in second.source
    assert "0210:missing_curve_value" in second.source


def test_current_values_keep_last_finite_sample_and_mark_missing_latest_row() -> None:
    runtime, _frames = _runtime_with_frames(
        (
            _frame(1, time_value="0315450", depth=100.0, rop=10.0),
            _frame(2, time_value="0315460", depth=100.2, rop=None),
        )
    )
    rop_id = _curve_id(runtime, "0210")
    view = AcquisitionLiveView(
        runtime.controller.dataset,
        runtime.session,
        config=AcquisitionLiveViewConfig(stale_after_seconds=60.0),
    )

    snapshot = view.snapshot(
        curve_ids=(rop_id,),
        now=datetime(2026, 7, 27, 3, 15, 50, tzinfo=timezone.utc),
    )
    current = snapshot.current_values[0]

    assert current.value == 10.0
    assert current.quality is AcquisitionLiveQuality.MISSING
    assert current.sample_row_index == 0
    assert current.latest_row_index == 1
    assert current.age_rows == 1
    assert "missing" in current.quality_codes


def test_auto_follow_pause_and_resume_do_not_stop_growing_dataset() -> None:
    runtime, frames = _runtime_with_frames(
        (
            _frame(1, time_value="0315450", depth=100.0, rop=10.0),
            _frame(2, time_value="0315460", depth=100.2, rop=11.0),
            _frame(3, time_value="0315470", depth=100.4, rop=12.0),
        )
    )
    rop_id = _curve_id(runtime, "0210")
    view = AcquisitionLiveView(
        runtime.controller.dataset,
        runtime.session,
        config=AcquisitionLiveViewConfig(time_window_seconds=1.0),
    )
    before = view.snapshot(curve_ids=(rop_id,))
    assert before.visible_row_count == 3
    assert before.window_end is not None
    assert before.window_start == before.window_end - 1.0

    view.pause()
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    # Replay the same prefix through the real parser so its sequence tracker reaches
    # exactly the same state as the live connection before the appended frame.
    for offset, raw in enumerate(
        (
            _frame(1, time_value="0315450", depth=100.0, rop=10.0),
            _frame(2, time_value="0315460", depth=100.2, rop=11.0),
            _frame(3, time_value="0315470", depth=100.4, rop=12.0),
        )
    ):
        processor.append(
            raw,
            received_at=f"2026-07-27T03:15:{45 + offset:02d}Z",
            source_ref="live.wits",
        )
    appended = processor.append(
        _frame(4, time_value="0315480", depth=100.6, rop=13.0),
        received_at="2026-07-27T03:15:48Z",
        source_ref="live.wits",
    )
    runtime.submit_frames(appended)
    runtime.flush()

    paused = view.snapshot(curve_ids=(rop_id,))
    assert len(runtime.controller.dataset.depth) == 4
    assert paused.visible_row_count == 3
    assert paused.paused is True

    view.resume()
    resumed = view.snapshot(curve_ids=(rop_id,))
    assert resumed.visible_row_count == 4
    assert resumed.paused is False
    assert resumed.current_values[0].value == 13.0


def test_history_downsampling_respects_budget_and_preserves_missing_breaks() -> None:
    frames = tuple(
        _frame(
            sequence=index + 1,
            time_value=f"0315{45 + index:02d}0",
            depth=100.0 + index * 0.1,
            rop=None if index in {5, 6, 7} else float(index),
        )
        for index in range(15)
    )
    runtime, _parsed = _runtime_with_frames(frames)
    rop_id = _curve_id(runtime, "0210")
    view = AcquisitionLiveView(runtime.controller.dataset, runtime.session)
    axis = runtime.controller.dataset.active_index.values.astype("datetime64[ns]").astype(np.int64)
    view.set_history_window(float(axis[0]) / 1e9, float(axis[-1]) / 1e9)

    snapshot = view.snapshot(curve_ids=(rop_id,), max_points_per_curve=8)
    series = snapshot.series[0]

    assert series.source_point_count == 15
    assert series.rendered_point_count <= 8
    assert any(np.isnan(value) for value in series.values)
    assert snapshot.auto_follow is False


def test_quality_and_gap_markers_include_source_axis_invalid_and_missing_spans() -> None:
    runtime, _frames = _runtime_with_frames(
        (
            _frame(1, time_value="0315450", depth=100.0, rop=10.0),
            _frame(2, time_value="0315460", depth=100.2, rop=None),
            _frame(3, time_value="0315470", depth=100.4, rop=11.0),
            _frame(6, time_value="0316000", depth=101.0, rop=12.0),
        )
    )
    rop_id = _curve_id(runtime, "0210")
    view = AcquisitionLiveView(
        runtime.controller.dataset,
        runtime.session,
        config=AcquisitionLiveViewConfig(time_window_seconds=3600.0),
    )

    snapshot = view.snapshot(curve_ids=(rop_id,))
    kinds = {marker.kind for marker in snapshot.markers}

    assert AcquisitionLiveMarkerKind.SOURCE_SEQUENCE_GAP in kinds
    assert AcquisitionLiveMarkerKind.AXIS_GAP in kinds
    assert AcquisitionLiveMarkerKind.MISSING_SPAN in kinds


def test_depth_mode_derives_read_only_axis_from_reviewed_depth_curve() -> None:
    runtime, _frames = _runtime_with_frames(
        (
            _frame(1, time_value="0315450", depth=100.0, rop=10.0),
            _frame(2, time_value="0315460", depth=100.2, rop=11.0),
        )
    )
    rop_id = _curve_id(runtime, "0210")
    view = AcquisitionLiveView(runtime.controller.dataset, runtime.session)

    view.set_axis_mode(AcquisitionLiveAxisMode.DEPTH)
    snapshot = view.snapshot(curve_ids=(rop_id,))

    assert snapshot.axis_mode is AcquisitionLiveAxisMode.DEPTH
    assert snapshot.index_mnemonic == "HOLE_DEPTH"
    assert snapshot.window_start == 100.0
    assert snapshot.window_end == 100.2
    assert snapshot.series[0].axis_values == (100.0, 100.2)


def test_time_mode_derives_utc_axis_from_received_at_for_depth_dataset() -> None:
    runtime, _frames = _runtime_with_frames(
        (
            _frame(1, time_value="0315450", depth=100.0, rop=10.0),
            _frame(2, time_value="0315460", depth=100.2, rop=11.0),
        ),
        index_candidate_id="field:0208",
    )
    rop_id = _curve_id(runtime, "0210")
    view = AcquisitionLiveView(runtime.controller.dataset, runtime.session)

    view.set_axis_mode(AcquisitionLiveAxisMode.TIME)
    snapshot = view.snapshot(curve_ids=(rop_id,))

    assert snapshot.axis_mode is AcquisitionLiveAxisMode.TIME
    assert snapshot.axis_is_datetime is True
    assert snapshot.index_mnemonic == "RECEIVED_AT"
    assert snapshot.window_end is not None
    assert snapshot.window_start is not None
    assert snapshot.window_end - snapshot.window_start == 1.0


def test_follow_span_updates_only_the_resolved_axis_window() -> None:
    runtime, _frames = _runtime_with_frames(
        (
            _frame(1, time_value="0315450", depth=100.0, rop=10.0),
            _frame(2, time_value="0315460", depth=100.2, rop=11.0),
        )
    )
    view = AcquisitionLiveView(runtime.controller.dataset, runtime.session)
    original_depth_window = view.config.depth_window

    view.set_follow_span(30.0)

    assert view.config.time_window_seconds == 30.0
    assert view.config.depth_window == original_depth_window
