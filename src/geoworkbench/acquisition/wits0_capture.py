from __future__ import annotations

import json
import os
import re
import socket
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Deque, TextIO, TypedDict, Unpack

from geoworkbench.acquisition.wits0 import (
    Wits0FrameTooLargeError,
    Wits0Profile,
    load_builtin_wits0_profile,
)
from geoworkbench.acquisition.wits0_reliability import (
    Wits0ConnectionJournal,
    Wits0ConnectionJournalRecord,
    Wits0DiskSpaceError,
    Wits0DiskSpaceGuard,
    Wits0DiskSpacePolicy,
    Wits0DiskSpaceState,
    Wits0RawRetentionManager,
    Wits0RawRetentionPolicy,
    Wits0RecoveryManifest,
    Wits0RecoveryChanges,
    Wits0RecoveryState,
    Wits0RecoveryStore,
    recover_wits0_raw_directory,
)
from geoworkbench.acquisition.wits0_parser import (
    Wits0DiagnosticSeverity,
    Wits0ParsedFrame,
    Wits0SequenceStatus,
    Wits0StreamProcessor,
)


class Wits0ConnectionMode(StrEnum):
    TCP_SERVER = "tcp_server"
    TCP_CLIENT = "tcp_client"


class Wits0CaptureState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    LISTENING = "listening"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RETRY_WAIT = "retry_wait"
    STOPPING = "stopping"
    FAILED = "failed"


class Wits0CaptureEventKind(StrEnum):
    STATE = "state"
    CONNECTION = "connection"
    DISCONNECTION = "disconnection"
    FRAME = "frame"
    DIAGNOSTIC = "diagnostic"
    RAW_SEGMENT = "raw_segment"
    WARNING = "warning"
    ERROR = "error"
    DISK = "disk"
    RETENTION = "retention"
    RECOVERY = "recovery"


@dataclass(frozen=True, slots=True)
class Wits0CaptureConfig:
    mode: Wits0ConnectionMode
    host: str
    port: int
    raw_directory: Path
    source_name: str = "geoscape"
    encoding: str = "ascii"
    connect_timeout_s: float = 5.0
    socket_timeout_s: float = 0.5
    reconnect_initial_s: float = 1.0
    reconnect_max_s: float = 30.0
    max_frame_bytes: int = 1_048_576
    raw_segment_bytes: int = 64 * 1024 * 1024
    event_capacity: int = 2_000
    disk_policy: Wits0DiskSpacePolicy = field(default_factory=Wits0DiskSpacePolicy)
    retention_policy: Wits0RawRetentionPolicy = field(default_factory=Wits0RawRetentionPolicy)
    recovery_enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.mode, Wits0ConnectionMode):
            raise ValueError("mode must use Wits0ConnectionMode")
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("host must be a non-empty string")
        if isinstance(self.port, bool) or not 1 <= self.port <= 65_535:
            raise ValueError("port must be in the range 1..65535")
        if not isinstance(self.raw_directory, Path):
            object.__setattr__(self, "raw_directory", Path(self.raw_directory))
        if not isinstance(self.source_name, str) or not self.source_name.strip():
            raise ValueError("source_name must be a non-empty string")
        if self.encoding.casefold() not in {"ascii", "latin-1", "cp1251", "utf-8"}:
            raise ValueError(f"Unsupported WITS0 encoding: {self.encoding}")
        for value, label in (
            (self.connect_timeout_s, "connect_timeout_s"),
            (self.socket_timeout_s, "socket_timeout_s"),
            (self.reconnect_initial_s, "reconnect_initial_s"),
            (self.reconnect_max_s, "reconnect_max_s"),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{label} must be positive")
        if self.reconnect_max_s < self.reconnect_initial_s:
            raise ValueError("reconnect_max_s must be >= reconnect_initial_s")
        if isinstance(self.max_frame_bytes, bool) or self.max_frame_bytes < 16:
            raise ValueError("max_frame_bytes must be at least 16")
        if isinstance(self.raw_segment_bytes, bool) or self.raw_segment_bytes < 1_024:
            raise ValueError("raw_segment_bytes must be at least 1024")
        if isinstance(self.event_capacity, bool) or self.event_capacity < 10:
            raise ValueError("event_capacity must be at least 10")
        if not isinstance(self.disk_policy, Wits0DiskSpacePolicy):
            raise ValueError("disk_policy must use Wits0DiskSpacePolicy")
        if not isinstance(self.retention_policy, Wits0RawRetentionPolicy):
            raise ValueError("retention_policy must use Wits0RawRetentionPolicy")
        if not isinstance(self.recovery_enabled, bool):
            raise ValueError("recovery_enabled must be a boolean")


@dataclass(frozen=True, slots=True)
class Wits0CaptureEvent:
    kind: Wits0CaptureEventKind
    occurred_at: str
    message: str = ""
    state: Wits0CaptureState | None = None
    peer: str | None = None
    frame: bytes | None = None
    parsed_frame: Wits0ParsedFrame | None = None
    raw_file: str | None = None
    connection_id: str | None = None
    reason: str | None = None
    disk_free_bytes: int | None = None
    bytes_received: int = 0
    frames_received: int = 0


@dataclass(frozen=True, slots=True)
class Wits0CaptureSnapshot:
    state: Wits0CaptureState = Wits0CaptureState.STOPPED
    started_at: str | None = None
    current_peer: str | None = None
    current_raw_file: str | None = None
    last_received_at: str | None = None
    bytes_received: int = 0
    frames_received: int = 0
    parsed_fields: int = 0
    parser_warnings: int = 0
    parser_errors: int = 0
    unknown_records: int = 0
    unknown_fields: int = 0
    sequence_gaps: int = 0
    sequence_duplicates: int = 0
    sequence_out_of_order: int = 0
    last_sequence: str | None = None
    connections: int = 0
    disconnects: int = 0
    errors: int = 0
    discarded_prefix_bytes: int = 0
    dropped_ui_events: int = 0
    current_connection_id: str | None = None
    disk_state: Wits0DiskSpaceState = Wits0DiskSpaceState.HEALTHY
    disk_free_bytes: int | None = None
    retention_segments_deleted: int = 0
    retention_bytes_deleted: int = 0
    recovery_sidecars_repaired: int = 0
    recovery_unclean_detected: bool = False


class _Wits0CaptureSnapshotChanges(TypedDict, total=False):
    current_peer: str | None
    current_raw_file: str | None
    last_received_at: str | None
    discarded_prefix_bytes: int
    current_connection_id: str | None
    disk_state: Wits0DiskSpaceState
    disk_free_bytes: int | None
    last_sequence: str | None


class _Wits0CaptureSnapshotIncrements(TypedDict, total=False):
    bytes_received: int
    frames_received: int
    parsed_fields: int
    parser_warnings: int
    parser_errors: int
    unknown_records: int
    unknown_fields: int
    sequence_gaps: int
    sequence_duplicates: int
    sequence_out_of_order: int
    connections: int
    disconnects: int
    errors: int
    dropped_ui_events: int
    retention_segments_deleted: int
    retention_bytes_deleted: int


class Wits0RawCaptureWriter:
    """Append-only WITS0 raw segments with a timestamp/offset JSONL sidecar."""

    def __init__(
        self,
        root: str | Path,
        *,
        source_name: str,
        connection_id: str,
        segment_bytes: int,
    ) -> None:
        self.root = Path(root)
        self.source_name = _safe_component(source_name)
        self.connection_id = _safe_component(connection_id)
        self.segment_bytes = int(segment_bytes)
        self._segment_no = 0
        self._size = 0
        self._data: BinaryIO | None = None
        self._index: TextIO | None = None
        self._data_path: Path | None = None

    @property
    def current_path(self) -> Path | None:
        return self._data_path

    def write(self, chunk: bytes, *, received_at: str) -> Path:
        if not chunk:
            raise ValueError("raw capture chunk must not be empty")
        if self._data is None or self._size + len(chunk) > self.segment_bytes:
            self._open_segment(received_at)
        assert self._data is not None and self._index is not None and self._data_path is not None
        offset = self._size
        self._data.write(chunk)
        self._data.flush()
        self._index.write(
            json.dumps(
                {
                    "receivedAt": received_at,
                    "offset": offset,
                    "size": len(chunk),
                    "connectionId": self.connection_id,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        self._index.flush()
        self._size += len(chunk)
        return self._data_path

    def close(self) -> None:
        for stream in (self._data, self._index):
            if stream is not None:
                try:
                    stream.flush()
                    os.fsync(stream.fileno())
                except OSError:
                    pass
                stream.close()
        self._data = None
        self._index = None
        self._data_path = None
        self._size = 0

    def _open_segment(self, received_at: str) -> None:
        self.close()
        self._segment_no += 1
        timestamp = _filename_timestamp(received_at)
        day = timestamp[:8]
        directory = self.root / day / self.source_name / self.connection_id
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"{timestamp}-segment-{self._segment_no:06d}"
        data_path = directory / f"{stem}.wits"
        index_path = directory / f"{stem}.chunks.jsonl"
        suffix = 0
        while data_path.exists() or index_path.exists():
            suffix += 1
            data_path = directory / f"{stem}-{suffix}.wits"
            index_path = directory / f"{stem}-{suffix}.chunks.jsonl"
        self._data = data_path.open("xb")
        self._index = index_path.open("x", encoding="utf-8", newline="\n")
        self._data_path = data_path
        self._size = 0

    def __enter__(self) -> Wits0RawCaptureWriter:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        self.close()


class Wits0CaptureEngine:
    """Headless WITS0 TCP client/server raw capture service.

    The worker owns all socket I/O.  Consumers only poll immutable events and snapshots, so Qt
    widgets never touch a socket and the project model is not mutated by this first capture slice.
    """

    def __init__(
        self,
        config: Wits0CaptureConfig,
        *,
        profile: Wits0Profile | None = None,
    ) -> None:
        self.config = config
        self.profile = profile or load_builtin_wits0_profile()
        if self.profile.encoding.casefold() != config.encoding.casefold():
            raise ValueError(
                "WITS0 capture encoding must match the selected parser profile"
            )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket_lock = threading.Lock()
        self._active_socket: socket.socket | None = None
        self._events: Deque[Wits0CaptureEvent] = deque(maxlen=config.event_capacity)
        self._events_lock = threading.Lock()
        self._snapshot = Wits0CaptureSnapshot()
        self._snapshot_lock = threading.Lock()
        self.run_id = uuid.uuid4().hex
        self._disk_guard = Wits0DiskSpaceGuard(
            config.raw_directory,
            policy=config.disk_policy,
        )
        self._retention = Wits0RawRetentionManager(config.retention_policy)
        reliability_root = config.raw_directory / _safe_component(config.source_name)
        self._journal = Wits0ConnectionJournal(reliability_root / "connections.jsonl")
        self._recovery_store = Wits0RecoveryStore(reliability_root / ".wits0-recovery.json")
        self._manifest: Wits0RecoveryManifest | None = None
        self._last_disk_state: Wits0DiskSpaceState | None = None

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("WITS0 capture is already running")
        self.config.raw_directory.mkdir(parents=True, exist_ok=True)
        previous = self._recovery_store.load() if self.config.recovery_enabled else None
        recovery = (
            recover_wits0_raw_directory(self.config.raw_directory)
            if self.config.recovery_enabled
            else None
        )
        disk = self._disk_guard.require_writable(force=True)
        retention = self._retention.apply(self.config.raw_directory)
        self._stop.clear()
        started_at = _utc_now()
        with self._snapshot_lock:
            self._snapshot = Wits0CaptureSnapshot(
                state=Wits0CaptureState.STARTING,
                started_at=started_at,
                disk_state=disk.state,
                disk_free_bytes=disk.free_bytes,
                retention_segments_deleted=retention.segments_deleted,
                retention_bytes_deleted=retention.bytes_deleted,
                recovery_sidecars_repaired=(recovery.sidecars_repaired if recovery else 0),
                recovery_unclean_detected=bool(previous and previous.unclean),
            )
        self._last_disk_state = disk.state
        if self.config.recovery_enabled:
            self._manifest = Wits0RecoveryManifest(
                run_id=self.run_id,
                state=Wits0RecoveryState.STARTING,
                clean_shutdown=False,
                process_id=os.getpid(),
                started_at=started_at,
                updated_at=started_at,
                mode=self.config.mode.value,
                host=self.config.host,
                port=self.config.port,
                source_name=self.config.source_name,
                raw_directory=str(self.config.raw_directory),
            )
            self._recovery_store.save(self._manifest)
        if previous is not None and previous.unclean:
            self._emit(
                Wits0CaptureEvent(
                    kind=Wits0CaptureEventKind.RECOVERY,
                    occurred_at=started_at,
                    message=(
                        "Detected unclean WITS0 shutdown; raw sidecars were checked "
                        f"(repaired={recovery.sidecars_repaired if recovery else 0})"
                    ),
                    reason=previous.failure or previous.state.value,
                )
            )
        if retention.segments_deleted:
            self._emit(
                Wits0CaptureEvent(
                    kind=Wits0CaptureEventKind.RETENTION,
                    occurred_at=started_at,
                    message=(
                        f"Raw retention deleted {retention.segments_deleted} segment(s), "
                        f"{retention.bytes_deleted} bytes"
                    ),
                )
            )
        self._journal.append(
            Wits0ConnectionJournalRecord(
                event="run_started",
                occurred_at=started_at,
                run_id=self.run_id,
                connection_id=None,
                mode=self.config.mode.value,
                endpoint=f"{self.config.host}:{self.config.port}",
                peer=None,
            )
        )
        self._emit_state(Wits0CaptureState.STARTING, "WITS0 capture is starting")
        self._thread = threading.Thread(
            target=self._run,
            name=f"wits0-{self.config.mode.value}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, timeout: float = 3.0) -> bool:
        if not self.is_running:
            self._set_state(Wits0CaptureState.STOPPED)
            return True
        self._emit_state(Wits0CaptureState.STOPPING, "WITS0 capture is stopping")
        self._stop.set()
        with self._socket_lock:
            active = self._active_socket
            if active is not None:
                try:
                    active.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    active.close()
                except OSError:
                    pass
        assert self._thread is not None
        self._thread.join(timeout=max(0.0, timeout))
        return not self._thread.is_alive()

    def snapshot(self) -> Wits0CaptureSnapshot:
        with self._snapshot_lock:
            return replace(self._snapshot)

    def drain_events(self, *, max_events: int = 250) -> tuple[Wits0CaptureEvent, ...]:
        if isinstance(max_events, bool) or max_events < 1:
            raise ValueError("max_events must be positive")
        items: list[Wits0CaptureEvent] = []
        with self._events_lock:
            while self._events and len(items) < max_events:
                items.append(self._events.popleft())
        return tuple(items)

    def set_recovery_context(
        self,
        *,
        acquisition_session_id: str | None,
        custom_profile_path: str | None,
    ) -> None:
        self._update_manifest(
            acquisition_session_id=acquisition_session_id,
            custom_profile_path=custom_profile_path,
        )

    def _run(self) -> None:
        failure: str | None = None
        try:
            self._update_manifest(state=Wits0RecoveryState.RUNNING)
            if self.config.mode is Wits0ConnectionMode.TCP_SERVER:
                self._run_server()
            else:
                self._run_client()
        except Wits0DiskSpaceError as exc:
            failure = str(exc)
            self._record_error(failure)
            self._set_state(Wits0CaptureState.FAILED)
            self._emit(
                Wits0CaptureEvent(
                    kind=Wits0CaptureEventKind.DISK,
                    occurred_at=_utc_now(),
                    message=failure,
                    disk_free_bytes=(
                        self._disk_guard.last_snapshot.free_bytes
                        if self._disk_guard.last_snapshot is not None
                        else None
                    ),
                    reason="critical_free_space",
                )
            )
        except Exception as exc:  # defensive worker boundary
            failure = str(exc)
            self._record_error(f"WITS0 worker failed: {exc}")
            self._set_state(Wits0CaptureState.FAILED)
        finally:
            self._replace_active_socket(None)
            stopped_at = _utc_now()
            if self.snapshot().state is not Wits0CaptureState.FAILED:
                self._emit_state(Wits0CaptureState.STOPPED, "WITS0 capture stopped")
                self._update_manifest(
                    state=Wits0RecoveryState.STOPPED,
                    clean_shutdown=True,
                    current_connection_id=None,
                    current_peer=None,
                    current_raw_file=None,
                )
            else:
                self._update_manifest(
                    state=Wits0RecoveryState.FAILED,
                    clean_shutdown=False,
                    failure=failure or "worker_failed",
                )
            self._journal.append(
                Wits0ConnectionJournalRecord(
                    event="run_stopped" if failure is None else "run_failed",
                    occurred_at=stopped_at,
                    run_id=self.run_id,
                    connection_id=None,
                    mode=self.config.mode.value,
                    endpoint=f"{self.config.host}:{self.config.port}",
                    peer=None,
                    reason=failure,
                    bytes_received=self.snapshot().bytes_received,
                    frames_received=self.snapshot().frames_received,
                )
            )

    def _run_server(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.settimeout(self.config.socket_timeout_s)
        self._replace_active_socket(listener)
        try:
            listener.bind((self.config.host, self.config.port))
            listener.listen(1)
            self._emit_state(
                Wits0CaptureState.LISTENING,
                f"Listening on {self.config.host}:{self.config.port}",
            )
            while not self._stop.is_set():
                try:
                    connection, address = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop.is_set():
                        break
                    raise
                peer = f"{address[0]}:{address[1]}"
                self._replace_active_socket(connection)
                self._capture_connection(connection, peer)
                if self._stop.is_set():
                    break
                self._replace_active_socket(listener)
                self._emit_state(
                    Wits0CaptureState.LISTENING,
                    f"Listening on {self.config.host}:{self.config.port}",
                )
        finally:
            try:
                listener.close()
            except OSError:
                pass

    def _run_client(self) -> None:
        delay = self.config.reconnect_initial_s
        while not self._stop.is_set():
            self._emit_state(
                Wits0CaptureState.CONNECTING,
                f"Connecting to {self.config.host}:{self.config.port}",
            )
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection.settimeout(self.config.connect_timeout_s)
            self._replace_active_socket(connection)
            try:
                connection.connect((self.config.host, self.config.port))
            except OSError as exc:
                try:
                    connection.close()
                except OSError:
                    pass
                if self._stop.is_set():
                    break
                self._record_error(
                    f"Cannot connect to {self.config.host}:{self.config.port}: {exc}"
                )
                self._emit_state(
                    Wits0CaptureState.RETRY_WAIT,
                    f"Reconnect in {delay:g} s",
                )
                if self._stop.wait(delay):
                    break
                delay = min(delay * 2.0, self.config.reconnect_max_s)
                continue
            delay = self.config.reconnect_initial_s
            self._capture_connection(
                connection,
                f"{self.config.host}:{self.config.port}",
            )

    def _capture_connection(self, connection: socket.socket, peer: str) -> None:
        connection.settimeout(self.config.socket_timeout_s)
        connection_id = uuid.uuid4().hex
        processor = Wits0StreamProcessor(
            self.profile,
            max_frame_bytes=self.config.max_frame_bytes,
        )
        writer = Wits0RawCaptureWriter(
            self.config.raw_directory,
            source_name=self.config.source_name,
            connection_id=connection_id,
            segment_bytes=self.config.raw_segment_bytes,
        )
        start_snapshot = self.snapshot()
        connected_at = _utc_now()
        disconnect_reason = "remote_closed"
        self._increment_snapshot(connections=1)
        self._set_snapshot_fields(
            current_peer=peer,
            current_connection_id=connection_id,
        )
        self._update_manifest(
            current_connection_id=connection_id,
            current_peer=peer,
        )
        self._emit_state(Wits0CaptureState.CONNECTED, f"Connected: {peer}")
        self._emit(
            Wits0CaptureEvent(
                kind=Wits0CaptureEventKind.CONNECTION,
                occurred_at=connected_at,
                message="WITS0 TCP connection established",
                peer=peer,
                connection_id=connection_id,
            )
        )
        self._journal.append(
            Wits0ConnectionJournalRecord(
                event="connected",
                occurred_at=connected_at,
                run_id=self.run_id,
                connection_id=connection_id,
                mode=self.config.mode.value,
                endpoint=f"{self.config.host}:{self.config.port}",
                peer=peer,
            )
        )
        last_file: Path | None = None
        try:
            while not self._stop.is_set():
                try:
                    chunk = connection.recv(65_536)
                except socket.timeout:
                    self._check_disk_space(require_writable=True)
                    continue
                except OSError as exc:
                    disconnect_reason = "local_stop" if self._stop.is_set() else f"socket_error:{exc}"
                    if not self._stop.is_set():
                        self._record_error(f"WITS0 receive error from {peer}: {exc}")
                    break
                if not chunk:
                    disconnect_reason = "remote_closed"
                    break
                disk = self._check_disk_space(require_writable=True)
                received_at = _utc_now()
                raw_file = writer.write(chunk, received_at=received_at)
                if raw_file != last_file:
                    last_file = raw_file
                    self._set_snapshot_fields(current_raw_file=str(raw_file))
                    self._update_manifest(current_raw_file=str(raw_file))
                    retention = self._retention.apply(
                        self.config.raw_directory,
                        protected_paths=(raw_file,),
                    )
                    if retention.segments_deleted:
                        self._increment_snapshot(
                            retention_segments_deleted=retention.segments_deleted,
                            retention_bytes_deleted=retention.bytes_deleted,
                        )
                        self._emit(
                            Wits0CaptureEvent(
                                kind=Wits0CaptureEventKind.RETENTION,
                                occurred_at=received_at,
                                message=(
                                    f"Raw retention deleted {retention.segments_deleted} segment(s), "
                                    f"{retention.bytes_deleted} bytes"
                                ),
                                connection_id=connection_id,
                            )
                        )
                    self._emit(
                        Wits0CaptureEvent(
                            kind=Wits0CaptureEventKind.RAW_SEGMENT,
                            occurred_at=received_at,
                            message="Raw WITS0 segment opened",
                            peer=peer,
                            raw_file=str(raw_file),
                            connection_id=connection_id,
                            disk_free_bytes=disk.free_bytes,
                        )
                    )
                self._increment_snapshot(bytes_received=len(chunk))
                self._set_snapshot_fields(last_received_at=received_at)
                self._update_manifest(
                    last_received_at=received_at,
                    current_raw_file=str(raw_file),
                )
                try:
                    frames = processor.append(
                        chunk,
                        received_at=received_at,
                        source_ref=str(raw_file),
                    )
                except Wits0FrameTooLargeError as exc:
                    self._set_snapshot_fields(
                        discarded_prefix_bytes=processor.discarded_bytes,
                    )
                    processor = Wits0StreamProcessor(
                        self.profile,
                        max_frame_bytes=self.config.max_frame_bytes,
                    )
                    self._record_warning(str(exc), peer=peer)
                    continue
                for parsed_frame in frames:
                    self._record_parsed_frame(
                        parsed_frame,
                        peer=peer,
                        raw_file=raw_file,
                    )
                with self._snapshot_lock:
                    self._snapshot = replace(
                        self._snapshot,
                        discarded_prefix_bytes=processor.discarded_bytes,
                    )
        except Wits0DiskSpaceError:
            disconnect_reason = "critical_free_space"
            raise
        finally:
            pending = processor.reset()
            if pending:
                self._record_warning(
                    f"Connection ended with {len(pending)} incomplete WITS0 bytes",
                    peer=peer,
                )
            final_raw = writer.current_path
            writer.close()
            try:
                connection.close()
            except OSError:
                pass
            self._increment_snapshot(disconnects=1)
            current = self.snapshot()
            disconnected_at = _utc_now()
            connection_bytes = max(0, current.bytes_received - start_snapshot.bytes_received)
            connection_frames = max(0, current.frames_received - start_snapshot.frames_received)
            self._set_snapshot_fields(
                current_peer=None,
                current_raw_file=None,
                current_connection_id=None,
            )
            self._update_manifest(
                current_connection_id=None,
                current_peer=None,
                current_raw_file=None,
            )
            self._emit(
                Wits0CaptureEvent(
                    kind=Wits0CaptureEventKind.DISCONNECTION,
                    occurred_at=disconnected_at,
                    message="WITS0 TCP connection closed",
                    peer=peer,
                    raw_file=str(final_raw) if final_raw is not None else None,
                    connection_id=connection_id,
                    reason=disconnect_reason,
                    bytes_received=connection_bytes,
                    frames_received=connection_frames,
                )
            )
            self._journal.append(
                Wits0ConnectionJournalRecord(
                    event="disconnected",
                    occurred_at=disconnected_at,
                    run_id=self.run_id,
                    connection_id=connection_id,
                    mode=self.config.mode.value,
                    endpoint=f"{self.config.host}:{self.config.port}",
                    peer=peer,
                    reason=disconnect_reason,
                    raw_file=str(final_raw) if final_raw is not None else None,
                    bytes_received=connection_bytes,
                    frames_received=connection_frames,
                )
            )

    def _record_parsed_frame(
        self,
        parsed_frame: Wits0ParsedFrame,
        *,
        peer: str,
        raw_file: Path,
    ) -> None:
        increments: _Wits0CaptureSnapshotIncrements = {
            "frames_received": 1,
            "parsed_fields": len(parsed_frame.fields),
            "parser_warnings": parsed_frame.warning_count,
            "parser_errors": parsed_frame.error_count,
            "unknown_records": parsed_frame.unknown_record_count,
            "unknown_fields": parsed_frame.unknown_field_count,
            "sequence_gaps": int(
                parsed_frame.sequence_status is Wits0SequenceStatus.GAP
            ),
            "sequence_duplicates": int(
                parsed_frame.sequence_status is Wits0SequenceStatus.DUPLICATE
            ),
            "sequence_out_of_order": int(
                parsed_frame.sequence_status is Wits0SequenceStatus.OUT_OF_ORDER
            ),
        }
        self._increment_snapshot(**increments)
        if parsed_frame.record_no is not None and parsed_frame.sequence_no is not None:
            self._set_snapshot_fields(
                last_sequence=(
                    f"{parsed_frame.record_no:02d}:{parsed_frame.sequence_no}"
                )
            )
        self._emit(
            Wits0CaptureEvent(
                kind=Wits0CaptureEventKind.FRAME,
                occurred_at=parsed_frame.received_at or _utc_now(),
                message=(
                    f"WITS0 record {parsed_frame.record_no:02d} parsed"
                    if parsed_frame.record_no is not None
                    else "WITS0 mixed/unknown frame parsed"
                ),
                peer=peer,
                frame=parsed_frame.raw_frame,
                parsed_frame=parsed_frame,
                raw_file=str(raw_file),
                connection_id=self.snapshot().current_connection_id,
            )
        )
        for diagnostic in parsed_frame.diagnostics:
            if diagnostic.severity is Wits0DiagnosticSeverity.INFO:
                continue
            self._emit(
                Wits0CaptureEvent(
                    kind=Wits0CaptureEventKind.DIAGNOSTIC,
                    occurred_at=parsed_frame.received_at or _utc_now(),
                    message=f"{diagnostic.code.value}: {diagnostic.message}",
                    peer=peer,
                    parsed_frame=parsed_frame,
                    raw_file=str(raw_file),
                    connection_id=self.snapshot().current_connection_id,
                )
            )

    def _replace_active_socket(self, value: socket.socket | None) -> None:
        with self._socket_lock:
            self._active_socket = value

    def _check_disk_space(
        self,
        *,
        require_writable: bool = False,
    ):
        snapshot = (
            self._disk_guard.require_writable()
            if require_writable
            else self._disk_guard.check()
        )
        self._set_snapshot_fields(
            disk_state=snapshot.state,
            disk_free_bytes=snapshot.free_bytes,
        )
        if snapshot.state is not self._last_disk_state:
            self._last_disk_state = snapshot.state
            self._emit(
                Wits0CaptureEvent(
                    kind=Wits0CaptureEventKind.DISK,
                    occurred_at=snapshot.checked_at,
                    message=(
                        f"WITS0 disk state={snapshot.state.value}; "
                        f"free={snapshot.free_bytes} bytes"
                    ),
                    disk_free_bytes=snapshot.free_bytes,
                    reason=snapshot.state.value,
                )
            )
        return snapshot

    def _update_manifest(self, **changes: Unpack[Wits0RecoveryChanges]) -> None:
        manifest = self._manifest
        if manifest is None:
            return
        try:
            self._manifest = self._recovery_store.update(manifest, **changes)
        except OSError as exc:
            self._record_warning(f"Cannot update WITS0 recovery manifest: {exc}")

    def _emit_state(self, state: Wits0CaptureState, message: str) -> None:
        self._set_state(state)
        self._emit(
            Wits0CaptureEvent(
                kind=Wits0CaptureEventKind.STATE,
                occurred_at=_utc_now(),
                message=message,
                state=state,
            )
        )

    def _set_state(self, state: Wits0CaptureState) -> None:
        with self._snapshot_lock:
            self._snapshot = replace(self._snapshot, state=state)

    def _set_snapshot_fields(
        self,
        **changes: Unpack[_Wits0CaptureSnapshotChanges],
    ) -> None:
        with self._snapshot_lock:
            self._snapshot = replace(self._snapshot, **changes)

    def _increment_snapshot(
        self,
        **increments: Unpack[_Wits0CaptureSnapshotIncrements],
    ) -> None:
        with self._snapshot_lock:
            changes = {
                key: getattr(self._snapshot, key) + value
                for key, value in increments.items()
            }
            self._snapshot = replace(self._snapshot, **changes)

    def _record_warning(self, message: str, *, peer: str | None = None) -> None:
        self._emit(
            Wits0CaptureEvent(
                kind=Wits0CaptureEventKind.WARNING,
                occurred_at=_utc_now(),
                message=message,
                peer=peer,
            )
        )

    def _record_error(self, message: str) -> None:
        self._increment_snapshot(errors=1)
        self._emit(
            Wits0CaptureEvent(
                kind=Wits0CaptureEventKind.ERROR,
                occurred_at=_utc_now(),
                message=message,
            )
        )

    def _emit(self, event: Wits0CaptureEvent) -> None:
        with self._events_lock:
            was_full = len(self._events) == self._events.maxlen
            self._events.append(event)
        if was_full:
            self._increment_snapshot(dropped_ui_events=1)


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip(".-")
    return cleaned[:80] or "source"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _filename_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
