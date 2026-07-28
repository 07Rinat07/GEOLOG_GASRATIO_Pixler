from __future__ import annotations

import json
import os
import socket
import threading
import time
from io import BytesIO
from pathlib import Path, PurePath

import pytest

from geoworkbench.acquisition import (
    Wits0CaptureConfig,
    Wits0CaptureEngine,
    Wits0CaptureEventKind,
    Wits0CaptureState,
    Wits0ConnectionMode,
    Wits0FrameDecoder,
    Wits0FrameTooLargeError,
    Wits0ProfileError,
    WITS0_RAW_DIRECTORY_MARKER_NAME,
    Wits0RawCaptureWriter,
    Wits0RemoteBindPolicy,
    Wits0RawRetentionPolicy,
    inspect_wits0_raw_directory,
    iter_wits0_frames,
    load_builtin_wits0_profile,
    load_wits0_profile,
)


def test_frame_decoder_handles_tcp_chunk_boundaries_and_multiple_frames() -> None:
    decoder = Wits0FrameDecoder(max_frame_bytes=128)

    assert decoder.append(b"noise&") == ()
    assert decoder.append(b"&\r\n010812.3\r\n!") == ()
    frames = decoder.append(b"!\r\n&&0208100!!tail&&03081")

    assert frames == (b"&&\r\n010812.3\r\n!!", b"&&0208100!!")
    assert decoder.discarded_bytes == len(b"noise") + len(b"\r\ntail")
    assert decoder.buffered_bytes == len(b"&&03081")
    assert decoder.append(b"00!!") == (b"&&0308100!!",)


def test_frame_decoder_rejects_unbounded_incomplete_frame_and_recovers() -> None:
    decoder = Wits0FrameDecoder(max_frame_bytes=16)

    with pytest.raises(Wits0FrameTooLargeError, match="exceeded"):
        decoder.append(b"&&" + b"1" * 20)

    assert decoder.buffered_bytes == 0
    assert decoder.append(b"&&01081!!") == (b"&&01081!!",)


def test_replay_uses_the_same_incremental_decoder() -> None:
    source = BytesIO(b"prefix&&01081!!\r\n&&02082!!suffix")

    frames = tuple(iter_wits0_frames(source, chunk_size=3))

    assert frames == (b"&&01081!!", b"&&02082!!")


def test_replay_accepts_generic_pathlike_sources(tmp_path: Path) -> None:
    source = tmp_path / "capture.wits"
    source.write_bytes(b"prefix&&01081!!\r\n&&02082!!suffix")

    frames = tuple(iter_wits0_frames(PurePath(source), chunk_size=3))

    assert frames == (b"&&01081!!", b"&&02082!!")


def test_builtin_geoscape_profile_matches_manual_record_inventory() -> None:
    profile = load_builtin_wits0_profile()

    assert profile.profile_id == "geoscape-gswits"
    assert profile.start_marker == "&&"
    assert profile.end_marker == "!!"
    assert {record.record_no for record in profile.records} == {
        1,
        2,
        3,
        6,
        7,
        8,
        11,
        12,
        13,
        14,
        17,
    }
    assert profile.record(1).field(40).canonical_mnemonic == "TG_AVG"  # type: ignore[union-attr]
    assert profile.record(2).field(10).canonical_mnemonic == "ROP"  # type: ignore[union-attr]
    assert profile.record(12).field(18).canonical_mnemonic == "NC5"  # type: ignore[union-attr]
    assert profile.record(13).index_type == "depth_lagged"  # type: ignore[union-attr]


def test_profile_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    source = tmp_path / "bad.json"
    source.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "profileId": "bad",
                "title": "Bad",
                "version": 1,
                "encoding": "ascii",
                "frame": {"start": "&&", "end": "!!"},
                "records": [],
                "unexpected": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(Wits0ProfileError, match="unknown fields"):
        load_wits0_profile(source)


def test_raw_writer_is_append_only_and_records_chunk_offsets(tmp_path: Path) -> None:
    writer = Wits0RawCaptureWriter(
        tmp_path,
        source_name="GeoScape rig 1",
        connection_id="connection-1",
        segment_bytes=12,
    )

    first = writer.write(b"&&01081!!", received_at="2026-07-27T00:00:00.000Z")
    second = writer.write(b"&&02082!!", received_at="2026-07-27T00:00:01.000Z")
    writer.close()

    assert first != second
    assert first.read_bytes() == b"&&01081!!"
    assert second.read_bytes() == b"&&02082!!"
    assert "GeoScape-rig-1" in first.parts
    sidecar = first.with_suffix(".chunks.jsonl")
    metadata = json.loads(sidecar.read_text(encoding="utf-8").strip())
    assert metadata == {
        "receivedAt": "2026-07-27T00:00:00.000Z",
        "offset": 0,
        "size": 9,
        "connectionId": "connection-1",
    }


def test_tcp_server_capture_writes_raw_stream_and_emits_complete_frames(
    tmp_path: Path,
) -> None:
    port = _free_tcp_port()
    engine = Wits0CaptureEngine(
        Wits0CaptureConfig(
            mode=Wits0ConnectionMode.TCP_SERVER,
            host="127.0.0.1",
            port=port,
            raw_directory=tmp_path,
            source_name="test-source",
            socket_timeout_s=0.05,
            raw_segment_bytes=1024,
        )
    )
    engine.start()
    _wait_until(lambda: engine.snapshot().state is Wits0CaptureState.LISTENING)

    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as client:
        client.sendall(b"garbage&")
        client.sendall(b"&\r\n010812.3\r\n!")
        client.sendall(b"!&&0208100!!")

    _wait_until(lambda: engine.snapshot().frames_received == 2)
    assert engine.stop(timeout=2.0)
    _wait_until(lambda: engine.snapshot().state is Wits0CaptureState.STOPPED)

    snapshot = engine.snapshot()
    events = engine.drain_events(max_events=500)
    frame_events = [
        item for item in events if item.kind is Wits0CaptureEventKind.FRAME
    ]
    frames = [item.frame for item in frame_events]
    raw_files = sorted(tmp_path.rglob("*.wits"))

    assert frames == [b"&&\r\n010812.3\r\n!!", b"&&0208100!!"]
    assert all(item.parsed_frame is not None for item in frame_events)
    assert snapshot.connections == 1
    assert snapshot.disconnects == 1
    assert snapshot.bytes_received == len(b"garbage&&\r\n010812.3\r\n!!&&0208100!!")
    assert snapshot.discarded_prefix_bytes == len(b"garbage")
    assert snapshot.parsed_fields == 2
    assert snapshot.parser_warnings >= 2  # both minimal frames omit sequence field 04
    assert len(raw_files) == 1
    assert raw_files[0].read_bytes() == b"garbage&&\r\n010812.3\r\n!!&&0208100!!"
    assert (tmp_path / WITS0_RAW_DIRECTORY_MARKER_NAME).is_file()
    assert inspect_wits0_raw_directory(tmp_path).verified
    assert raw_files[0].with_suffix(".chunks.jsonl").exists()


def test_tcp_client_capture_connects_and_writes_raw_stream(tmp_path: Path) -> None:
    ready = threading.Event()
    accepted = threading.Event()
    port_holder: list[int] = []

    def serve() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port_holder.append(int(listener.getsockname()[1]))
            ready.set()
            connection, _ = listener.accept()
            accepted.set()
            with connection:
                connection.sendall(b"&&01081!!")

    server = threading.Thread(target=serve, name="wits0-test-server", daemon=True)
    server.start()
    assert ready.wait(timeout=2.0)

    engine = Wits0CaptureEngine(
        Wits0CaptureConfig(
            mode=Wits0ConnectionMode.TCP_CLIENT,
            host="127.0.0.1",
            port=port_holder[0],
            raw_directory=tmp_path,
            source_name="test-client",
            connect_timeout_s=0.5,
            socket_timeout_s=0.05,
            reconnect_initial_s=0.05,
            reconnect_max_s=0.1,
            raw_segment_bytes=1024,
        )
    )
    engine.start()
    assert accepted.wait(timeout=2.0)
    _wait_until(lambda: engine.snapshot().frames_received == 1)
    assert engine.stop(timeout=2.0)
    server.join(timeout=2.0)

    events = engine.drain_events(max_events=500)
    frames = [item.frame for item in events if item.kind is Wits0CaptureEventKind.FRAME]
    raw_files = sorted(tmp_path.rglob("*.wits"))

    assert frames == [b"&&01081!!"]
    assert engine.snapshot().connections == 1
    assert raw_files and raw_files[0].read_bytes() == b"&&01081!!"



def test_unowned_existing_directory_keeps_capture_but_disables_retention(
    tmp_path: Path,
) -> None:
    old_segment = tmp_path / "old.wits"
    old_segment.write_bytes(b"keep")
    os.utime(old_segment, (1, 1))
    engine = Wits0CaptureEngine(
        Wits0CaptureConfig(
            mode=Wits0ConnectionMode.TCP_SERVER,
            host="127.0.0.1",
            port=_free_tcp_port(),
            raw_directory=tmp_path,
            socket_timeout_s=0.05,
            retention_policy=Wits0RawRetentionPolicy(
                max_age_days=1,
                max_total_bytes=1,
                keep_min_segments=0,
            ),
        )
    )

    engine.start()
    _wait_until(lambda: engine.snapshot().state is Wits0CaptureState.LISTENING)
    assert engine.stop(timeout=2.0)
    events = engine.drain_events(max_events=500)

    assert old_segment.exists()
    assert any(
        event.kind is Wits0CaptureEventKind.WARNING
        and event.reason == "marker_missing"
        for event in events
    )


def test_remote_server_rejects_peer_outside_allowlist(tmp_path: Path) -> None:
    port = _free_tcp_port()
    engine = Wits0CaptureEngine(
        Wits0CaptureConfig(
            mode=Wits0ConnectionMode.TCP_SERVER,
            host="0.0.0.0",
            port=port,
            raw_directory=tmp_path,
            socket_timeout_s=0.05,
            remote_bind_policy=Wits0RemoteBindPolicy(
                allowed_peer_networks=("10.0.0.0/8",),
                warning_acknowledged=True,
                allow_wildcard_bind=True,
            ),
        )
    )

    engine.start()
    _wait_until(lambda: engine.snapshot().state is Wits0CaptureState.LISTENING)
    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as client:
        client.sendall(b"&&01081!!")
    _wait_until(
        lambda: any(
            event.reason == "peer_not_allowlisted"
            for event in engine.drain_events(max_events=500)
        )
    )
    assert engine.stop(timeout=2.0)

    assert engine.snapshot().connections == 0
    assert not list(tmp_path.rglob("*.wits"))
    journal = next(tmp_path.rglob("connections.jsonl"))
    records = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert any(item["event"] == "connection_rejected" for item in records)


def test_remote_server_bind_requires_acknowledged_peer_allowlist(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="explicit network policy"):
        Wits0CaptureConfig(
            mode=Wits0ConnectionMode.TCP_SERVER,
            host="192.168.10.5",
            port=2041,
            raw_directory=tmp_path,
        )

    with pytest.raises(ValueError, match="warning acknowledgement"):
        Wits0CaptureConfig(
            mode=Wits0ConnectionMode.TCP_SERVER,
            host="192.168.10.5",
            port=2041,
            raw_directory=tmp_path,
            remote_bind_policy=Wits0RemoteBindPolicy(
                allowed_peer_networks=("192.168.10.0/24",),
            ),
        )

    config = Wits0CaptureConfig(
        mode=Wits0ConnectionMode.TCP_SERVER,
        host="192.168.10.5",
        port=2041,
        raw_directory=tmp_path,
        remote_bind_policy=Wits0RemoteBindPolicy(
            allowed_peer_networks=("192.168.10.0/24", "192.168.10.7/32"),
            warning_acknowledged=True,
        ),
    )

    assert config.remote_bind_policy is not None
    assert config.remote_bind_policy.allowed_peer_networks == ("192.168.10.0/24",)
    assert config.remote_bind_policy.allows_peer("192.168.10.44")
    assert not config.remote_bind_policy.allows_peer("192.168.11.1")


def test_remote_bind_policy_rejects_global_or_unbounded_networks() -> None:
    with pytest.raises(ValueError, match="isolated non-global"):
        Wits0RemoteBindPolicy(
            allowed_peer_networks=("0.0.0.0/0",),
            warning_acknowledged=True,
        )
    with pytest.raises(ValueError, match="isolated non-global"):
        Wits0RemoteBindPolicy(
            allowed_peer_networks=("8.8.8.0/24",),
            warning_acknowledged=True,
        )


def test_wildcard_server_bind_requires_explicit_policy_flag(tmp_path: Path) -> None:
    policy = Wits0RemoteBindPolicy(
        allowed_peer_networks=("10.40.0.0/16",),
        warning_acknowledged=True,
    )
    with pytest.raises(ValueError, match="allow_wildcard_bind"):
        Wits0CaptureConfig(
            mode=Wits0ConnectionMode.TCP_SERVER,
            host="0.0.0.0",
            port=2041,
            raw_directory=tmp_path,
            remote_bind_policy=policy,
        )

    config = Wits0CaptureConfig(
        mode=Wits0ConnectionMode.TCP_SERVER,
        host="0.0.0.0",
        port=2041,
        raw_directory=tmp_path,
        remote_bind_policy=Wits0RemoteBindPolicy(
            allowed_peer_networks=("10.40.0.0/16",),
            warning_acknowledged=True,
            allow_wildcard_bind=True,
        ),
    )
    assert config.remote_bind_policy is not None
    assert config.remote_bind_policy.allow_wildcard_bind


def test_loopback_server_and_remote_client_do_not_require_bind_policy(tmp_path: Path) -> None:
    loopback = Wits0CaptureConfig(
        mode=Wits0ConnectionMode.TCP_SERVER,
        host="127.0.0.1",
        port=2041,
        raw_directory=tmp_path,
    )
    client = Wits0CaptureConfig(
        mode=Wits0ConnectionMode.TCP_CLIENT,
        host="192.0.2.15",
        port=2041,
        raw_directory=tmp_path,
    )

    assert loopback.remote_bind_policy is None
    assert client.remote_bind_policy is None

def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_until(predicate, *, timeout: float = 3.0) -> None:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for WITS0 capture state")
