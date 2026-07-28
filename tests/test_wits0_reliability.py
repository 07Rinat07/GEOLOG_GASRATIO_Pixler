from __future__ import annotations

import json
import os
from collections import namedtuple
from pathlib import Path

import pytest

from geoworkbench.acquisition import (
    Wits0ConnectionJournal,
    Wits0ConnectionJournalRecord,
    Wits0DiskSpaceError,
    Wits0DiskSpaceGuard,
    Wits0DiskSpacePolicy,
    Wits0DiskSpaceState,
    WITS0_RAW_DIRECTORY_MARKER_NAME,
    Wits0RawRetentionManager,
    Wits0RawRetentionPolicy,
    Wits0RecoveryManifest,
    Wits0RecoveryState,
    Wits0RecoveryStore,
    Wits0StreamProcessor,
    Wits0WorkspaceSettings,
    Wits0WorkspaceState,
    initialize_wits0_raw_directory,
    inspect_wits0_raw_directory,
    load_builtin_wits0_profile,
    recover_wits0_raw_directory,
)
from geoworkbench.domain.models import Project, Well
from geoworkbench.domain.operational_events import (
    ConnectionEventPayload,
    OperationalEventKind,
)
from geoworkbench.services.wits0_acquisition import Wits0AcquisitionRuntime
from geoworkbench.services.wits0_import_review import (
    Wits0DiscoveryAccumulator,
    Wits0ImportReviewController,
)
from geoworkbench.services.wits0_recovery import (
    open_wits0_sessions,
    restore_wits0_import_review_commit,
)
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import load_project


_DiskUsage = namedtuple("_DiskUsage", "total used free")


class _Settings:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.sync_count = 0

    def value(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def setValue(self, key: str, value: object) -> None:
        self.values[key] = value

    def sync(self) -> None:
        self.sync_count += 1


def _frame(sequence: int = 1) -> bytes:
    return (
        "&&\r\n"
        "0201SG-8\r\n"
        "020201\r\n"
        "020302\r\n"
        f"0204{sequence}\r\n"
        "0205260727\r\n"
        "02060315450\r\n"
        "0208123.4\r\n"
        "021011.2\r\n"
        "!!"
    ).encode("ascii")


def _commit():  # type: ignore[no-untyped-def]
    profile = load_builtin_wits0_profile()
    frames = Wits0StreamProcessor(profile).append(
        _frame(),
        received_at="2026-07-27T03:15:45Z",
        source_ref="fixture.wits",
    )
    discovery = Wits0DiscoveryAccumulator(profile)
    discovery.observe_many(frames)
    snapshot = discovery.snapshot()
    controller = Wits0ImportReviewController()
    commit = controller.commit(snapshot, profile, controller.initial_plan(snapshot))
    return frames[0], commit


def test_disk_space_guard_is_rate_limited_and_stops_on_critical_space(tmp_path: Path) -> None:
    readings = iter(
        (
            _DiskUsage(1000, 100, 900),
            _DiskUsage(1000, 850, 150),
            _DiskUsage(1000, 950, 50),
        )
    )
    clocks = iter((0.0, 0.5, 2.0, 4.0))
    calls = 0

    def usage(_root: object) -> object:
        nonlocal calls
        calls += 1
        return next(readings)

    guard = Wits0DiskSpaceGuard(
        tmp_path,
        policy=Wits0DiskSpacePolicy(
            critical_free_bytes=100,
            warning_free_bytes=200,
            check_interval_seconds=1.0,
        ),
        usage_provider=usage,
        monotonic=lambda: next(clocks),
    )

    assert guard.check().state is Wits0DiskSpaceState.HEALTHY
    assert guard.check().state is Wits0DiskSpaceState.HEALTHY
    assert calls == 1
    assert guard.check().state is Wits0DiskSpaceState.WARNING
    with pytest.raises(Wits0DiskSpaceError, match="disk-space guard"):
        guard.require_writable()
    assert calls == 3


def test_raw_retention_deletes_oldest_complete_segments_and_sidecars(
    tmp_path: Path,
) -> None:
    initialize_wits0_raw_directory(tmp_path)
    paths = []
    for index in range(4):
        path = tmp_path / f"segment-{index}.wits"
        path.write_bytes(b"x" * 10)
        path.with_suffix(".chunks.jsonl").write_text("{}\n", encoding="utf-8")
        os.utime(path, (100 + index, 100 + index))
        paths.append(path)
    manager = Wits0RawRetentionManager(
        Wits0RawRetentionPolicy(
            max_age_days=1,
            max_total_bytes=15,
            keep_min_segments=1,
        )
    )

    result = manager.apply(tmp_path, protected_paths=(paths[2],), now=10 * 86_400)

    assert result.segments_deleted == 2
    assert result.bytes_deleted == 20
    assert not paths[0].exists()
    assert not paths[1].exists()
    assert paths[2].exists()
    assert paths[3].exists()
    assert not paths[0].with_suffix(".chunks.jsonl").exists()


def test_raw_retention_fails_closed_without_application_marker(tmp_path: Path) -> None:
    segment = tmp_path / "segment.wits"
    segment.write_bytes(b"raw")
    os.utime(segment, (1, 1))
    manager = Wits0RawRetentionManager(
        Wits0RawRetentionPolicy(max_age_days=1, max_total_bytes=1, keep_min_segments=0)
    )

    result = manager.apply(tmp_path, now=10 * 86_400)

    assert segment.exists()
    assert result.segments_deleted == 0
    assert not result.ownership_verified
    assert result.skip_reason == "marker_missing"


def test_raw_directory_marker_requires_explicit_adoption_for_nonempty_directory(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "operator-notes.txt"
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="explicitly adopted"):
        initialize_wits0_raw_directory(tmp_path)

    ownership = initialize_wits0_raw_directory(tmp_path, adopt_existing=True)

    assert ownership.verified
    assert existing.read_text(encoding="utf-8") == "keep"
    assert (tmp_path / WITS0_RAW_DIRECTORY_MARKER_NAME).is_file()
    assert inspect_wits0_raw_directory(tmp_path).ownership_id == ownership.ownership_id


def test_copied_raw_directory_marker_does_not_authorize_another_path(
    tmp_path: Path,
) -> None:
    owned = tmp_path / "owned"
    other = tmp_path / "other"
    initialize_wits0_raw_directory(owned)
    other.mkdir()
    (other / WITS0_RAW_DIRECTORY_MARKER_NAME).write_bytes(
        (owned / WITS0_RAW_DIRECTORY_MARKER_NAME).read_bytes()
    )
    segment = other / "segment.wits"
    segment.write_bytes(b"raw")

    result = Wits0RawRetentionManager(
        Wits0RawRetentionPolicy(max_age_days=1, max_total_bytes=1, keep_min_segments=0)
    ).apply(other, now=10 * 86_400)

    assert segment.exists()
    assert result.skip_reason == "marker_owner_mismatch"


def test_corrupt_raw_directory_marker_blocks_retention(tmp_path: Path) -> None:
    marker = tmp_path / WITS0_RAW_DIRECTORY_MARKER_NAME
    marker.write_text("not-json", encoding="utf-8")
    segment = tmp_path / "segment.wits"
    segment.write_bytes(b"raw")
    manager = Wits0RawRetentionManager(
        Wits0RawRetentionPolicy(max_age_days=1, max_total_bytes=1, keep_min_segments=0)
    )

    result = manager.apply(tmp_path, now=10 * 86_400)

    assert segment.exists()
    assert result.skip_reason == "marker_invalid_json"
    with pytest.raises(ValueError, match="marker is invalid"):
        initialize_wits0_raw_directory(tmp_path, adopt_existing=True)


def test_raw_recovery_repairs_crash_truncated_sidecar_without_touching_raw(
    tmp_path: Path,
) -> None:
    data = tmp_path / "capture.wits"
    original = b"abcdefghij"
    data.write_bytes(original)
    sidecar = data.with_suffix(".chunks.jsonl")
    sidecar.write_bytes(
        b'{"offset":0,"size":4}\n'
        b'{"offset":4,"size":3}\n'
        b'{"offset":7,"siz'
    )
    orphan = tmp_path / "orphan.chunks.jsonl"
    orphan.write_text('{"offset":0,"size":1}\n', encoding="utf-8")

    report = recover_wits0_raw_directory(tmp_path)

    assert data.read_bytes() == original
    assert sidecar.read_text(encoding="utf-8").splitlines() == [
        '{"offset":0,"size":4}',
        '{"offset":4,"size":3}',
    ]
    assert report.sidecars_repaired == 1
    assert report.orphan_sidecars == 1
    assert report.unindexed_tail_bytes == 3


def test_recovery_manifest_round_trip_and_unclean_detection(tmp_path: Path) -> None:
    store = Wits0RecoveryStore(tmp_path / ".wits0-recovery.json")
    manifest = Wits0RecoveryManifest(
        run_id="run-1",
        state=Wits0RecoveryState.RUNNING,
        clean_shutdown=False,
        process_id=123,
        started_at="2026-07-27T03:00:00.000Z",
        updated_at="2026-07-27T03:00:00.000Z",
        mode="tcp_server",
        host="127.0.0.1",
        port=2041,
        source_name="source",
        raw_directory=str(tmp_path),
    )

    store.save(manifest)
    loaded = store.load()
    assert loaded == manifest
    assert loaded is not None and loaded.unclean

    stopped = store.update(
        loaded,
        state=Wits0RecoveryState.STOPPED,
        clean_shutdown=True,
    )
    assert not stopped.unclean
    assert store.load() == stopped


def test_connection_journal_is_append_only_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "connections.jsonl"
    journal = Wits0ConnectionJournal(path)
    first = Wits0ConnectionJournalRecord(
        event="connected",
        occurred_at="2026-07-27T03:00:00.000Z",
        run_id="run-1",
        connection_id="connection-1",
        mode="tcp_server",
        endpoint="127.0.0.1:2041",
        peer="127.0.0.1:50000",
    )
    second = Wits0ConnectionJournalRecord(
        event="disconnected",
        occurred_at="2026-07-27T03:01:00.000Z",
        run_id="run-1",
        connection_id="connection-1",
        mode="tcp_server",
        endpoint="127.0.0.1:2041",
        peer="127.0.0.1:50000",
        reason="remote_closed",
        bytes_received=100,
        frames_received=4,
    )

    journal.append(first)
    journal.append(second)

    payloads = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [item["event"] for item in payloads] == ["connected", "disconnected"]
    assert payloads[1]["frames_received"] == 4


def test_workspace_settings_round_trip_and_reject_invalid_payload() -> None:
    settings = _Settings()
    store = Wits0WorkspaceSettings(settings)
    state = Wits0WorkspaceState(
        axis_mode="depth",
        auto_follow=False,
        paused=True,
        follow_span=250.0,
        max_points=4000,
        selected_curve_ids=("curve-a", "curve-b"),
        history_start=100.0,
        history_end=200.0,
        acquisition_session_id="session-1",
    )

    store.save("well/1", state)

    assert store.load("well/1") == state
    assert settings.sync_count == 1
    settings.values["wits0/workspace/well_1"] = "not-json"
    assert store.load("well/1") == Wits0WorkspaceState()


def test_connection_events_are_append_only_and_survive_project_round_trip(
    tmp_path: Path,
) -> None:
    frame, commit = _commit()
    well = Well("well-1", "Well 1")
    runtime = Wits0AcquisitionRuntime(well, commit, session_id="session-1")

    runtime.submit_connection_event(
        connected=True,
        occurred_at="2026-07-27T03:00:00Z",
        connection_id="connection-1",
        peer="127.0.0.1:50000",
    )
    runtime.submit_frame(frame)
    runtime.submit_connection_event(
        connected=False,
        occurred_at="2026-07-27T03:01:00Z",
        connection_id="connection-1",
        peer="127.0.0.1:50000",
        reason="remote_closed",
        raw_file="capture.wits",
        bytes_received=100,
        frames_received=1,
    )
    runtime.flush()

    assert runtime.session.last_sequence == 3
    connection_events = [
        item
        for item in well.operational_events.values()
        if item.kind is OperationalEventKind.CONNECTION
    ]
    assert len(connection_events) == 2
    disconnected = next(
        item for item in connection_events if item.payload.state == "disconnected"
    )
    assert isinstance(disconnected.payload, ConnectionEventPayload)
    assert disconnected.payload.bytes_received == 100

    target = tmp_path / "project.geolog.json"
    save_project(Project("project-1", "Project", wells={well.well_id: well}), target)
    loaded = load_project(target)
    loaded_events = loaded.wells[well.well_id].operational_events.values()
    restored = [item for item in loaded_events if item.kind is OperationalEventKind.CONNECTION]
    assert len(restored) == 2
    assert all(isinstance(item.payload, ConnectionEventPayload) for item in restored)


def test_open_wits0_session_can_be_recovered_and_sequence_continues(
    tmp_path: Path,
) -> None:
    frame, commit = _commit()
    well = Well("well-1", "Well 1")
    runtime = Wits0AcquisitionRuntime(well, commit, session_id="session-1")
    runtime.submit_frame(frame)
    runtime.flush()
    target = tmp_path / "project.geolog.json"
    save_project(Project("project-1", "Project", wells={well.well_id: well}), target)

    loaded = load_project(target)
    loaded_well = loaded.wells[well.well_id]
    sessions = open_wits0_sessions(loaded_well)
    assert [item.session_id for item in sessions] == ["session-1"]
    restored_commit = restore_wits0_import_review_commit(
        sessions[0],
        commit.custom_profile,
    )
    resumed = Wits0AcquisitionRuntime(
        loaded_well,
        restored_commit,
        session_id="session-1",
        session=sessions[0],
    )
    resumed.submit_connection_event(
        connected=True,
        occurred_at="2026-07-27T03:02:00Z",
        connection_id="connection-2",
    )
    resumed.flush()

    assert resumed.session.last_sequence == 2
    assert resumed.snapshot().records_applied == 2


def test_capture_engine_marks_unclean_previous_run_and_finishes_cleanly(
    tmp_path: Path,
) -> None:
    import socket
    import time

    from geoworkbench.acquisition import (
        Wits0CaptureConfig,
        Wits0CaptureEngine,
        Wits0CaptureState,
        Wits0ConnectionMode,
    )

    source_root = tmp_path / "source"
    source_root.mkdir(parents=True)
    previous = Wits0RecoveryManifest(
        run_id="previous",
        state=Wits0RecoveryState.RUNNING,
        clean_shutdown=False,
        process_id=1,
        started_at="2026-07-27T03:00:00.000Z",
        updated_at="2026-07-27T03:00:00.000Z",
        mode="tcp_server",
        host="127.0.0.1",
        port=2041,
        source_name="source",
        raw_directory=str(tmp_path),
    )
    Wits0RecoveryStore(source_root / ".wits0-recovery.json").save(previous)
    raw = tmp_path / "unfinished.wits"
    raw.write_bytes(b"abcdef")
    raw.with_suffix(".chunks.jsonl").write_bytes(
        b'{"offset":0,"size":3}\n{"offset":3,"siz'
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    engine = Wits0CaptureEngine(
        Wits0CaptureConfig(
            mode=Wits0ConnectionMode.TCP_SERVER,
            host="127.0.0.1",
            port=port,
            raw_directory=tmp_path,
            source_name="source",
            socket_timeout_s=0.05,
        )
    )

    engine.start()
    deadline = time.monotonic() + 2.0
    while engine.snapshot().state is not Wits0CaptureState.LISTENING:
        if time.monotonic() >= deadline:
            raise AssertionError("capture engine did not start listening")
        time.sleep(0.01)
    snapshot = engine.snapshot()
    assert snapshot.recovery_unclean_detected
    assert snapshot.recovery_sidecars_repaired == 1
    assert engine.stop(timeout=2.0)

    manifest = Wits0RecoveryStore(source_root / ".wits0-recovery.json").load()
    assert manifest is not None
    assert manifest.state is Wits0RecoveryState.STOPPED
    assert manifest.clean_shutdown
    events = [
        json.loads(line)["event"]
        for line in (source_root / "connections.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert events == ["run_started", "run_stopped"]
