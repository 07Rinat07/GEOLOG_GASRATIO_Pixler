from __future__ import annotations

import json
from pathlib import Path

import pytest

from geoworkbench.acquisition import (
    Wits0RawCaptureWriter,
    Wits0StreamProcessor,
    load_builtin_wits0_profile,
)
from geoworkbench.domain.models import Well
from geoworkbench.services.wits0_acquisition import (
    Wits0AcquisitionConfig,
    Wits0AcquisitionRuntime,
    Wits0BackpressurePolicy,
)
from geoworkbench.services.wits0_import_review import (
    Wits0DiscoveryAccumulator,
    Wits0ImportReviewController,
)
from geoworkbench.services.wits0_raw_replay import (
    Wits0RawReplayError,
    inspect_wits0_raw_replay,
    replay_wits0_raw_interval,
)


def _frame(record: int, sequence: int, *lines: str) -> bytes:
    return "\r\n".join(
        (
            "&&",
            f"{record:02d}01SG-8",
            f"{record:02d}0201",
            f"{record:02d}03{record}",
            f"{record:02d}04{sequence}",
            f"{record:02d}05260924",
            f"{record:02d}06150000",
            f"{record:02d}070",
            *lines,
            "!!",
        )
    ).encode("ascii")


def _commit(*raw_frames: bytes):  # type: ignore[no-untyped-def]
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    parsed = []
    for index, raw in enumerate(raw_frames):
        parsed.extend(
            processor.append(
                raw,
                received_at=f"2026-09-24T15:00:0{index + 1}Z",
                source_ref="fixture.wits",
            )
        )
    discovery = Wits0DiscoveryAccumulator(profile)
    discovery.observe_many(parsed)
    snapshot = discovery.snapshot()
    review = Wits0ImportReviewController()
    commit = review.commit(snapshot, profile, review.initial_plan(snapshot))
    return profile, commit


def _raw_fixture(tmp_path: Path) -> tuple[bytes, bytes]:
    first = _frame(2, 1, "0208123.4", "021011.2")
    second = _frame(2, 2, "0208123.6", "021012.0")
    writer = Wits0RawCaptureWriter(
        tmp_path,
        source_name="GeoScape rig 1",
        connection_id="connection-1",
        segment_bytes=10_000,
    )
    writer.write(
        first[:17],
        received_at="2026-09-24T15:00:01Z",
    )
    writer.write(
        first[17:] + second[:21],
        received_at="2026-09-24T15:00:02Z",
    )
    writer.write(
        second[21:],
        received_at="2026-09-24T15:00:03Z",
    )
    writer.close()
    return first, second


def test_raw_replay_inspection_reports_explicit_indexed_interval(tmp_path: Path) -> None:
    _raw_fixture(tmp_path)

    availability = inspect_wits0_raw_replay(
        tmp_path,
        source_name="GeoScape rig 1",
        start_at="2026-09-24T15:00:01Z",
        end_at="2026-09-24T15:00:03Z",
    )

    assert availability.available is True
    assert availability.covers_requested_interval is True
    assert availability.chunk_count == 3
    assert availability.segment_count == 1
    assert availability.earliest_received_at == "2026-09-24T15:00:01.000000Z"
    assert availability.latest_received_at == "2026-09-24T15:00:03.000000Z"
    assert availability.indexed_bytes > 0


def test_raw_replay_streams_through_live_parser_and_reviewed_runtime(
    tmp_path: Path,
) -> None:
    first, second = _raw_fixture(tmp_path)
    profile, commit = _commit(first, second)
    well = Well("well-1", "Well 1")
    runtime = Wits0AcquisitionRuntime(
        well,
        commit,
        session_id="session-raw-replay",
        config=Wits0AcquisitionConfig(
            max_pending_records=1,
            drain_batch_size=1,
            checkpoint_every_records=100,
            checkpoint_interval_seconds=3600.0,
            backpressure_policy=Wits0BackpressurePolicy.DRAIN_THEN_RETRY,
        ),
    )

    result = replay_wits0_raw_interval(
        runtime,
        profile=profile,
        raw_directory=tmp_path,
        source_name="GeoScape rig 1",
        start_at="2026-09-24T15:00:02Z",
        end_at="2026-09-24T15:00:03Z",
    )

    assert result.frames_selected == 2
    assert result.frames_accepted == 2
    assert result.frames_skipped == 0
    assert result.source_segments == 1
    assert result.first_selected_at == "2026-09-24T15:00:02.000000Z"
    assert result.last_selected_at == "2026-09-24T15:00:03.000000Z"
    assert runtime.session.last_sequence == 2
    assert len(runtime.controller.dataset.active_index.values) == 2
    assert all("ref=" in record.source for record in runtime.session.records)


def test_later_boundary_warms_parser_but_persists_only_selected_tail(
    tmp_path: Path,
) -> None:
    first, second = _raw_fixture(tmp_path)
    profile, commit = _commit(first, second)
    well = Well("well-1", "Well 1")
    runtime = Wits0AcquisitionRuntime(
        well,
        commit,
        session_id="session-later-boundary",
    )

    result = replay_wits0_raw_interval(
        runtime,
        profile=profile,
        raw_directory=tmp_path,
        source_name="GeoScape rig 1",
        start_at="2026-09-24T15:00:03Z",
        end_at="2026-09-24T15:00:03Z",
    )

    assert result.frames_seen == 2
    assert result.frames_selected == 1
    assert result.frames_accepted == 1
    assert runtime.session.last_sequence == 1
    assert runtime.session.records[0].received_at == "2026-09-24T15:00:03.000000Z"


def test_raw_replay_refuses_incomplete_requested_boundary_before_mutation(
    tmp_path: Path,
) -> None:
    first, second = _raw_fixture(tmp_path)
    profile, commit = _commit(first, second)
    well = Well("well-incomplete", "Well incomplete")
    runtime = Wits0AcquisitionRuntime(
        well,
        commit,
        session_id="session-incomplete",
    )

    with pytest.raises(Wits0RawReplayError, match="does not cover"):
        replay_wits0_raw_interval(
            runtime,
            profile=profile,
            raw_directory=tmp_path,
            source_name="GeoScape rig 1",
            start_at="2026-09-24T15:00:00Z",
            end_at="2026-09-24T15:00:03Z",
        )

    assert runtime.session.last_sequence == 0
    assert len(runtime.controller.dataset.active_index.values) == 0


def test_raw_replay_fails_closed_on_non_contiguous_sidecar_offsets(
    tmp_path: Path,
) -> None:
    _raw_fixture(tmp_path)
    sidecar = next(tmp_path.rglob("*.chunks.jsonl"))
    rows = [
        json.loads(line)
        for line in sidecar.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows[1]["offset"] += 1
    sidecar.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(Wits0RawReplayError, match="Non-contiguous"):
        inspect_wits0_raw_replay(
            tmp_path,
            source_name="GeoScape rig 1",
        )
