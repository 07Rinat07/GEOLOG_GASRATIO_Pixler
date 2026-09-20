from __future__ import annotations

from geoworkbench.acquisition import Wits0StreamProcessor, load_builtin_wits0_profile
from geoworkbench.domain.models import Well
from geoworkbench.services.wits0_acquisition import Wits0AcquisitionRuntime
from geoworkbench.services.wits0_import_review import Wits0ImportReviewController
from geoworkbench.services.wits0_live_preview import (
    Wits0LivePreview,
    Wits0LivePreviewConfig,
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
