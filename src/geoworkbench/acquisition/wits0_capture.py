from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Deque

from geoworkbench.acquisition.wits0 import Wits0FrameDecoder, Wits0FrameTooLargeError


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
    RAW_SEGMENT = "raw_segment"
    WARNING = "warning"
    ERROR = "error"


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


@dataclass(frozen=True, slots=True)
class Wits0CaptureEvent:
    kind: Wits0CaptureEventKind
    occurred_at: str
    message: str = ""
    state: Wits0CaptureState | None = None
    peer: str | None = None
    frame: bytes | None = None
    raw_file: str | None = None


@dataclass(frozen=True, slots=True)
class Wits0CaptureSnapshot:
    state: Wits0CaptureState = Wits0CaptureState.STOPPED
    started_at: str | None = None
    current_peer: str | None = None
    current_raw_file: str | None = None
    last_received_at: str | None = None
    bytes_received: int = 0
    frames_received: int = 0
    connections: int = 0
    disconnects: int = 0
    errors: int = 0
    discarded_prefix_bytes: int = 0
    dropped_ui_events: int = 0


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
        self._data = None
        self._index = None
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

    def __init__(self, config: Wits0CaptureConfig) -> None:
        self.config = config
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket_lock = threading.Lock()
        self._active_socket: socket.socket | None = None
        self._events: Deque[Wits0CaptureEvent] = deque(maxlen=config.event_capacity)
        self._events_lock = threading.Lock()
        self._snapshot = Wits0CaptureSnapshot()
        self._snapshot_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            raise RuntimeError("WITS0 capture is already running")
        self._stop.clear()
        with self._snapshot_lock:
            self._snapshot = Wits0CaptureSnapshot(
                state=Wits0CaptureState.STARTING,
                started_at=_utc_now(),
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

    def _run(self) -> None:
        try:
            if self.config.mode is Wits0ConnectionMode.TCP_SERVER:
                self._run_server()
            else:
                self._run_client()
        except Exception as exc:  # defensive worker boundary
            self._record_error(f"WITS0 worker failed: {exc}")
            self._set_state(Wits0CaptureState.FAILED)
        finally:
            self._replace_active_socket(None)
            if self.snapshot().state is not Wits0CaptureState.FAILED:
                self._emit_state(Wits0CaptureState.STOPPED, "WITS0 capture stopped")

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
        decoder = Wits0FrameDecoder(max_frame_bytes=self.config.max_frame_bytes)
        writer = Wits0RawCaptureWriter(
            self.config.raw_directory,
            source_name=self.config.source_name,
            connection_id=connection_id,
            segment_bytes=self.config.raw_segment_bytes,
        )
        self._increment_snapshot(connections=1)
        self._set_snapshot_fields(current_peer=peer)
        self._emit_state(Wits0CaptureState.CONNECTED, f"Connected: {peer}")
        self._emit(
            Wits0CaptureEvent(
                kind=Wits0CaptureEventKind.CONNECTION,
                occurred_at=_utc_now(),
                message="WITS0 TCP connection established",
                peer=peer,
            )
        )
        last_file: Path | None = None
        try:
            while not self._stop.is_set():
                try:
                    chunk = connection.recv(65_536)
                except socket.timeout:
                    continue
                except OSError as exc:
                    if not self._stop.is_set():
                        self._record_error(f"WITS0 receive error from {peer}: {exc}")
                    break
                if not chunk:
                    break
                received_at = _utc_now()
                raw_file = writer.write(chunk, received_at=received_at)
                if raw_file != last_file:
                    last_file = raw_file
                    self._set_snapshot_fields(current_raw_file=str(raw_file))
                    self._emit(
                        Wits0CaptureEvent(
                            kind=Wits0CaptureEventKind.RAW_SEGMENT,
                            occurred_at=received_at,
                            message="Raw WITS0 segment opened",
                            peer=peer,
                            raw_file=str(raw_file),
                        )
                    )
                self._increment_snapshot(bytes_received=len(chunk))
                self._set_snapshot_fields(last_received_at=received_at)
                try:
                    frames = decoder.append(chunk)
                except Wits0FrameTooLargeError as exc:
                    self._set_snapshot_fields(
                        discarded_prefix_bytes=decoder.discarded_bytes,
                    )
                    decoder = Wits0FrameDecoder(max_frame_bytes=self.config.max_frame_bytes)
                    self._record_warning(str(exc), peer=peer)
                    continue
                for frame in frames:
                    self._increment_snapshot(frames_received=1)
                    self._emit(
                        Wits0CaptureEvent(
                            kind=Wits0CaptureEventKind.FRAME,
                            occurred_at=received_at,
                            message="WITS0 frame received",
                            peer=peer,
                            frame=frame,
                            raw_file=str(raw_file),
                        )
                    )
                with self._snapshot_lock:
                    self._snapshot = replace(
                        self._snapshot,
                        discarded_prefix_bytes=decoder.discarded_bytes,
                    )
        finally:
            pending = decoder.reset()
            if pending:
                self._record_warning(
                    f"Connection ended with {len(pending)} incomplete WITS0 bytes",
                    peer=peer,
                )
            writer.close()
            try:
                connection.close()
            except OSError:
                pass
            self._increment_snapshot(disconnects=1)
            self._set_snapshot_fields(current_peer=None, current_raw_file=None)
            self._emit(
                Wits0CaptureEvent(
                    kind=Wits0CaptureEventKind.DISCONNECTION,
                    occurred_at=_utc_now(),
                    message="WITS0 TCP connection closed",
                    peer=peer,
                )
            )

    def _replace_active_socket(self, value: socket.socket | None) -> None:
        with self._socket_lock:
            self._active_socket = value

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

    def _set_snapshot_fields(self, **changes: object) -> None:
        with self._snapshot_lock:
            self._snapshot = replace(self._snapshot, **changes)

    def _increment_snapshot(self, **increments: int) -> None:
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
