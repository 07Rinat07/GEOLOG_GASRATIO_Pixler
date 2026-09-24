from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from geoworkbench.acquisition.wits0 import Wits0Profile
from geoworkbench.acquisition.wits0_parser import Wits0StreamProcessor
from geoworkbench.domain.acquisition import (
    acquisition_timestamp_to_ns,
    canonical_acquisition_timestamp,
)
from geoworkbench.services.wits0_acquisition import Wits0AcquisitionRuntime


class Wits0RawReplayError(RuntimeError):
    """Raised when raw WITS0 provenance cannot be replayed safely."""


@dataclass(frozen=True, slots=True)
class Wits0RawReplayAvailability:
    earliest_received_at: str | None
    latest_received_at: str | None
    chunk_count: int
    segment_count: int
    indexed_bytes: int
    requested_start_at: str | None = None
    requested_end_at: str | None = None

    @property
    def available(self) -> bool:
        return self.chunk_count > 0

    @property
    def covers_requested_interval(self) -> bool:
        if not self.available:
            return False
        if self.requested_start_at is not None:
            assert self.earliest_received_at is not None
            if (
                acquisition_timestamp_to_ns(self.earliest_received_at)
                > acquisition_timestamp_to_ns(self.requested_start_at)
            ):
                return False
        if self.requested_end_at is not None:
            assert self.latest_received_at is not None
            if (
                acquisition_timestamp_to_ns(self.latest_received_at)
                < acquisition_timestamp_to_ns(self.requested_end_at)
            ):
                return False
        return True


@dataclass(frozen=True, slots=True)
class Wits0RawReplayResult:
    frames_seen: int
    frames_selected: int
    frames_accepted: int
    frames_skipped: int
    source_segments: int
    indexed_bytes_read: int
    first_selected_at: str | None
    last_selected_at: str | None


@dataclass(frozen=True, slots=True)
class _ChunkIndexEntry:
    received_at: str
    received_ns: int
    offset: int
    size: int
    connection_id: str


@dataclass(frozen=True, slots=True)
class _SegmentIndex:
    raw_path: Path
    sidecar_path: Path
    connection_id: str
    first_received_at: str
    first_received_ns: int
    last_received_at: str
    last_received_ns: int
    indexed_bytes: int


def inspect_wits0_raw_replay(
    raw_directory: str | Path,
    *,
    source_name: str,
    start_at: str | None = None,
    end_at: str | None = None,
) -> Wits0RawReplayAvailability:
    """Inspect indexed raw capture without loading raw payload bytes into memory."""

    start = canonical_acquisition_timestamp(start_at) if start_at is not None else None
    end = canonical_acquisition_timestamp(end_at) if end_at is not None else None
    if start is not None and end is not None:
        if acquisition_timestamp_to_ns(end) < acquisition_timestamp_to_ns(start):
            raise ValueError("end_at must be greater than or equal to start_at")

    start_ns = acquisition_timestamp_to_ns(start) if start is not None else None
    end_ns = acquisition_timestamp_to_ns(end) if end is not None else None
    earliest: str | None = None
    latest: str | None = None
    earliest_ns: int | None = None
    latest_ns: int | None = None
    chunks = 0
    segments = 0
    indexed_bytes = 0

    for segment in _segment_indexes(raw_directory, source_name=source_name):
        segment_selected = False
        for entry in _iter_chunk_index(segment.raw_path, segment.sidecar_path):
            if start_ns is not None and entry.received_ns < start_ns:
                continue
            if end_ns is not None and entry.received_ns > end_ns:
                continue
            segment_selected = True
            chunks += 1
            indexed_bytes += entry.size
            if earliest_ns is None or entry.received_ns < earliest_ns:
                earliest_ns = entry.received_ns
                earliest = entry.received_at
            if latest_ns is None or entry.received_ns > latest_ns:
                latest_ns = entry.received_ns
                latest = entry.received_at
        if segment_selected:
            segments += 1

    return Wits0RawReplayAvailability(
        earliest_received_at=earliest,
        latest_received_at=latest,
        chunk_count=chunks,
        segment_count=segments,
        indexed_bytes=indexed_bytes,
        requested_start_at=start,
        requested_end_at=end,
    )


def replay_wits0_raw_interval(
    runtime: Wits0AcquisitionRuntime,
    *,
    profile: Wits0Profile,
    raw_directory: str | Path,
    source_name: str,
    start_at: str,
    end_at: str,
) -> Wits0RawReplayResult:
    """Replay one explicit raw interval through the live WITS0 parsing contract.

    Processing is streaming and bounded. Each TCP connection gets its own
    Wits0StreamProcessor, matching live capture semantics. Chunks before the
    requested start are still fed into the processor as warm-up so frame boundaries
    and source sequence QC remain deterministic; only frames whose receive timestamp
    falls inside start_at..end_at are submitted to the reviewed runtime.
    """

    start = canonical_acquisition_timestamp(start_at)
    end = canonical_acquisition_timestamp(end_at)
    start_ns = acquisition_timestamp_to_ns(start)
    end_ns = acquisition_timestamp_to_ns(end)
    if end_ns < start_ns:
        raise ValueError("end_at must be greater than or equal to start_at")

    segments = _segment_indexes(raw_directory, source_name=source_name)
    if not segments:
        raise Wits0RawReplayError("No indexed WITS0 raw segments are available")

    frames_seen = 0
    frames_selected = 0
    frames_accepted = 0
    indexed_bytes_read = 0
    selected_segments: set[Path] = set()
    first_selected_at: str | None = None
    last_selected_at: str | None = None
    processor: Wits0StreamProcessor | None = None
    active_connection: str | None = None

    for segment in segments:
        if segment.first_received_ns > end_ns:
            break
        if processor is None or segment.connection_id != active_connection:
            processor = Wits0StreamProcessor(profile)
            active_connection = segment.connection_id
        with segment.raw_path.open("rb") as stream:
            for entry in _iter_chunk_index(segment.raw_path, segment.sidecar_path):
                if entry.received_ns > end_ns:
                    break
                stream.seek(entry.offset)
                chunk = stream.read(entry.size)
                if len(chunk) != entry.size:
                    raise Wits0RawReplayError(
                        f"Raw segment changed during replay: {segment.raw_path}"
                    )
                indexed_bytes_read += len(chunk)
                parsed = processor.append(
                    chunk,
                    received_at=entry.received_at,
                    source_ref=str(segment.raw_path),
                )
                frames_seen += len(parsed)
                for frame in parsed:
                    if frame.received_at is None:
                        continue
                    frame_ns = acquisition_timestamp_to_ns(frame.received_at)
                    if frame_ns < start_ns or frame_ns > end_ns:
                        continue
                    frames_selected += 1
                    selected_segments.add(segment.raw_path)
                    if first_selected_at is None:
                        first_selected_at = frame.received_at
                    last_selected_at = frame.received_at
                    result = runtime.submit_frame(frame)
                    if result.accepted:
                        frames_accepted += 1

    runtime.flush()
    return Wits0RawReplayResult(
        frames_seen=frames_seen,
        frames_selected=frames_selected,
        frames_accepted=frames_accepted,
        frames_skipped=frames_selected - frames_accepted,
        source_segments=len(selected_segments),
        indexed_bytes_read=indexed_bytes_read,
        first_selected_at=first_selected_at,
        last_selected_at=last_selected_at,
    )


def _segment_indexes(
    raw_directory: str | Path,
    *,
    source_name: str,
) -> tuple[_SegmentIndex, ...]:
    root = Path(raw_directory)
    if not root.is_dir() or root.is_symlink():
        return ()
    safe_source = _safe_component(source_name)
    found: list[_SegmentIndex] = []
    for day in root.iterdir():
        if not day.is_dir() or day.is_symlink():
            continue
        source_root = day / safe_source
        if not source_root.is_dir() or source_root.is_symlink():
            continue
        for sidecar in source_root.rglob("*.chunks.jsonl"):
            if sidecar.is_symlink() or not sidecar.is_file():
                continue
            raw_name = sidecar.name.removesuffix(".chunks.jsonl") + ".wits"
            raw_path = sidecar.with_name(raw_name)
            if raw_path.is_symlink() or not raw_path.is_file():
                raise Wits0RawReplayError(
                    f"Indexed WITS0 raw segment is missing: {raw_path}"
                )
            entries = _iter_chunk_index(raw_path, sidecar)
            try:
                first = next(entries)
            except StopIteration:
                continue
            last = first
            indexed_bytes = first.size
            for entry in entries:
                last = entry
                indexed_bytes += entry.size
            found.append(
                _SegmentIndex(
                    raw_path=raw_path,
                    sidecar_path=sidecar,
                    connection_id=first.connection_id,
                    first_received_at=first.received_at,
                    first_received_ns=first.received_ns,
                    last_received_at=last.received_at,
                    last_received_ns=last.received_ns,
                    indexed_bytes=indexed_bytes,
                )
            )
    return tuple(
        sorted(
            found,
            key=lambda item: (
                item.first_received_ns,
                str(item.raw_path),
            ),
        )
    )


def _iter_chunk_index(
    raw_path: Path,
    sidecar_path: Path,
) -> Iterator[_ChunkIndexEntry]:
    file_size = raw_path.stat().st_size
    expected_offset = 0
    connection_id: str | None = None
    previous_ns: int | None = None
    try:
        stream = sidecar_path.open("r", encoding="utf-8")
    except OSError as exc:
        raise Wits0RawReplayError(
            f"Cannot read WITS0 raw sidecar: {sidecar_path}"
        ) from exc
    with stream:
        for line_no, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise Wits0RawReplayError(
                    f"Invalid WITS0 raw sidecar JSON at {sidecar_path}:{line_no}"
                ) from exc
            if not isinstance(payload, dict):
                raise Wits0RawReplayError(
                    f"Invalid WITS0 raw sidecar row at {sidecar_path}:{line_no}"
                )
            received = payload.get("receivedAt")
            offset = payload.get("offset")
            size = payload.get("size")
            row_connection = payload.get("connectionId")
            if not isinstance(received, str) or not received.strip():
                raise Wits0RawReplayError(
                    f"Missing receivedAt at {sidecar_path}:{line_no}"
                )
            if (
                isinstance(offset, bool)
                or not isinstance(offset, int)
                or offset < 0
                or isinstance(size, bool)
                or not isinstance(size, int)
                or size < 1
            ):
                raise Wits0RawReplayError(
                    f"Invalid offset/size at {sidecar_path}:{line_no}"
                )
            if not isinstance(row_connection, str) or not row_connection.strip():
                raise Wits0RawReplayError(
                    f"Missing connectionId at {sidecar_path}:{line_no}"
                )
            canonical = canonical_acquisition_timestamp(received)
            received_ns = acquisition_timestamp_to_ns(canonical)
            if offset != expected_offset:
                raise Wits0RawReplayError(
                    f"Non-contiguous raw sidecar offsets at {sidecar_path}:{line_no}"
                )
            if offset + size > file_size:
                raise Wits0RawReplayError(
                    f"Raw sidecar points beyond segment size at {sidecar_path}:{line_no}"
                )
            if connection_id is None:
                connection_id = row_connection
            elif row_connection != connection_id:
                raise Wits0RawReplayError(
                    f"Mixed connection IDs in raw sidecar {sidecar_path}"
                )
            if previous_ns is not None and received_ns < previous_ns:
                raise Wits0RawReplayError(
                    f"Out-of-order raw timestamps in {sidecar_path}:{line_no}"
                )
            expected_offset = offset + size
            previous_ns = received_ns
            yield _ChunkIndexEntry(
                received_at=canonical,
                received_ns=received_ns,
                offset=offset,
                size=size,
                connection_id=row_connection,
            )


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip(".-")
    return cleaned[:80] or "source"


__all__ = [
    "Wits0RawReplayAvailability",
    "Wits0RawReplayError",
    "Wits0RawReplayResult",
    "inspect_wits0_raw_replay",
    "replay_wits0_raw_interval",
]
