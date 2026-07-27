from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Callable, Iterable, Protocol


WITS0_RECOVERY_SCHEMA_VERSION = 1
WITS0_WORKSPACE_SCHEMA_VERSION = 1


class Wits0DiskSpaceState(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class Wits0RecoveryState(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class Wits0DiskSpaceError(OSError):
    """Raised before a raw write when the configured free-space floor is crossed."""


@dataclass(frozen=True, slots=True)
class Wits0DiskSpaceSnapshot:
    state: Wits0DiskSpaceState
    total_bytes: int
    used_bytes: int
    free_bytes: int
    checked_at: str


@dataclass(frozen=True, slots=True)
class Wits0DiskSpacePolicy:
    critical_free_bytes: int = 512 * 1024 * 1024
    warning_free_bytes: int = 2 * 1024 * 1024 * 1024
    check_interval_seconds: float = 2.0

    def __post_init__(self) -> None:
        for value, label in (
            (self.critical_free_bytes, "critical_free_bytes"),
            (self.warning_free_bytes, "warning_free_bytes"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")
        if self.warning_free_bytes < self.critical_free_bytes:
            raise ValueError("warning_free_bytes must be >= critical_free_bytes")
        if (
            isinstance(self.check_interval_seconds, bool)
            or not isinstance(self.check_interval_seconds, (int, float))
            or self.check_interval_seconds <= 0
        ):
            raise ValueError("check_interval_seconds must be positive")


class Wits0DiskSpaceGuard:
    """Rate-limited disk-space guard suitable for the raw-capture worker thread."""

    def __init__(
        self,
        root: str | Path,
        *,
        policy: Wits0DiskSpacePolicy | None = None,
        usage_provider: Callable[[str | Path], object] = shutil.disk_usage,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.root = Path(root)
        self.policy = policy or Wits0DiskSpacePolicy()
        self._usage_provider = usage_provider
        self._monotonic = monotonic
        self._last_check_clock: float | None = None
        self._last_snapshot: Wits0DiskSpaceSnapshot | None = None

    @property
    def last_snapshot(self) -> Wits0DiskSpaceSnapshot | None:
        return self._last_snapshot

    def check(self, *, force: bool = False) -> Wits0DiskSpaceSnapshot:
        now = float(self._monotonic())
        if (
            not force
            and self._last_snapshot is not None
            and self._last_check_clock is not None
            and now - self._last_check_clock < self.policy.check_interval_seconds
        ):
            return self._last_snapshot
        self.root.mkdir(parents=True, exist_ok=True)
        usage = self._usage_provider(self.root)
        total = int(getattr(usage, "total"))
        used = int(getattr(usage, "used"))
        free = int(getattr(usage, "free"))
        state = (
            Wits0DiskSpaceState.CRITICAL
            if free < self.policy.critical_free_bytes
            else Wits0DiskSpaceState.WARNING
            if free < self.policy.warning_free_bytes
            else Wits0DiskSpaceState.HEALTHY
        )
        snapshot = Wits0DiskSpaceSnapshot(
            state=state,
            total_bytes=total,
            used_bytes=used,
            free_bytes=free,
            checked_at=_utc_now(),
        )
        self._last_check_clock = now
        self._last_snapshot = snapshot
        return snapshot

    def require_writable(self, *, force: bool = False) -> Wits0DiskSpaceSnapshot:
        snapshot = self.check(force=force)
        if snapshot.state is Wits0DiskSpaceState.CRITICAL:
            raise Wits0DiskSpaceError(
                "WITS0 raw capture stopped by disk-space guard: "
                f"free={snapshot.free_bytes} bytes, "
                f"required>={self.policy.critical_free_bytes} bytes"
            )
        return snapshot


@dataclass(frozen=True, slots=True)
class Wits0RawRetentionPolicy:
    max_age_days: int | None = 30
    max_total_bytes: int | None = 20 * 1024 * 1024 * 1024
    keep_min_segments: int = 4

    def __post_init__(self) -> None:
        if self.max_age_days is not None and (
            isinstance(self.max_age_days, bool)
            or not isinstance(self.max_age_days, int)
            or self.max_age_days < 1
        ):
            raise ValueError("max_age_days must be None or a positive integer")
        if self.max_total_bytes is not None and (
            isinstance(self.max_total_bytes, bool)
            or not isinstance(self.max_total_bytes, int)
            or self.max_total_bytes < 1
        ):
            raise ValueError("max_total_bytes must be None or a positive integer")
        if (
            isinstance(self.keep_min_segments, bool)
            or not isinstance(self.keep_min_segments, int)
            or self.keep_min_segments < 0
        ):
            raise ValueError("keep_min_segments must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class Wits0RawRetentionResult:
    segments_scanned: int
    segments_deleted: int
    bytes_deleted: int
    bytes_remaining: int
    deleted_paths: tuple[str, ...]


class Wits0RawRetentionManager:
    """Delete only complete, inactive ``.wits`` segments and their known sidecars."""

    def __init__(self, policy: Wits0RawRetentionPolicy | None = None) -> None:
        self.policy = policy or Wits0RawRetentionPolicy()

    def apply(
        self,
        root: str | Path,
        *,
        protected_paths: Iterable[str | Path] = (),
        now: float | None = None,
    ) -> Wits0RawRetentionResult:
        root_path = Path(root)
        protected = {Path(item).resolve() for item in protected_paths}
        current_time = time.time() if now is None else float(now)
        segments: list[tuple[Path, int, float]] = []
        for path in root_path.rglob("*.wits") if root_path.exists() else ():
            try:
                resolved = path.resolve()
                stat = path.stat()
            except OSError:
                continue
            if resolved in protected:
                continue
            segments.append((path, int(stat.st_size), float(stat.st_mtime)))
        segments.sort(key=lambda item: (item[2], str(item[0])))
        total = sum(item[1] for item in segments)
        deletable_count = max(0, len(segments) - self.policy.keep_min_segments)
        deleted: list[str] = []
        deleted_bytes = 0
        for index, (path, size, modified_at) in enumerate(segments):
            if index >= deletable_count:
                break
            age_due = (
                self.policy.max_age_days is not None
                and current_time - modified_at >= self.policy.max_age_days * 86_400
            )
            size_due = (
                self.policy.max_total_bytes is not None
                and total > self.policy.max_total_bytes
            )
            if not age_due and not size_due:
                continue
            for related in _segment_related_paths(path):
                try:
                    related.unlink(missing_ok=True)
                except OSError:
                    continue
            deleted.append(str(path))
            deleted_bytes += size
            total -= size
        return Wits0RawRetentionResult(
            segments_scanned=len(segments),
            segments_deleted=len(deleted),
            bytes_deleted=deleted_bytes,
            bytes_remaining=total,
            deleted_paths=tuple(deleted),
        )


@dataclass(frozen=True, slots=True)
class Wits0RawRecoveryReport:
    segments_scanned: int
    sidecars_repaired: int
    invalid_sidecars: int
    orphan_data_segments: int
    orphan_sidecars: int
    unindexed_tail_bytes: int
    recovered_at: str


def recover_wits0_raw_directory(root: str | Path) -> Wits0RawRecoveryReport:
    """Repair crash-truncated JSONL sidecars without changing raw WITS bytes."""

    root_path = Path(root)
    data_paths = set(root_path.rglob("*.wits")) if root_path.exists() else set()
    sidecars = set(root_path.rglob("*.chunks.jsonl")) if root_path.exists() else set()
    repaired = invalid = orphan_sidecars = unindexed_tail = 0
    for sidecar in sorted(sidecars):
        data_path = sidecar.with_name(sidecar.name.removesuffix(".chunks.jsonl") + ".wits")
        if not data_path.exists():
            orphan_sidecars += 1
            continue
        try:
            raw_lines = sidecar.read_bytes().splitlines(keepends=True)
            data_size = data_path.stat().st_size
        except OSError:
            invalid += 1
            continue
        valid_lines: list[bytes] = []
        covered_end = 0
        bad = False
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped.decode("utf-8"))
                offset = int(item["offset"])
                size = int(item["size"])
            except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
                bad = True
                break
            if offset < 0 or size <= 0 or offset + size > data_size or offset < covered_end:
                bad = True
                break
            covered_end = offset + size
            valid_lines.append(stripped + b"\n")
        if bad or b"".join(valid_lines) != sidecar.read_bytes():
            try:
                _atomic_write_bytes(sidecar, b"".join(valid_lines))
            except OSError:
                invalid += 1
            else:
                repaired += 1
        unindexed_tail += max(0, data_size - covered_end)
    sidecar_data_paths = {
        path.with_name(path.name.removesuffix(".chunks.jsonl") + ".wits")
        for path in sidecars
    }
    orphan_data = len(data_paths.difference(sidecar_data_paths))
    return Wits0RawRecoveryReport(
        segments_scanned=len(data_paths),
        sidecars_repaired=repaired,
        invalid_sidecars=invalid,
        orphan_data_segments=orphan_data,
        orphan_sidecars=orphan_sidecars,
        unindexed_tail_bytes=unindexed_tail,
        recovered_at=_utc_now(),
    )


@dataclass(frozen=True, slots=True)
class Wits0RecoveryManifest:
    run_id: str
    state: Wits0RecoveryState
    clean_shutdown: bool
    process_id: int
    started_at: str
    updated_at: str
    mode: str
    host: str
    port: int
    source_name: str
    raw_directory: str
    current_connection_id: str | None = None
    current_peer: str | None = None
    current_raw_file: str | None = None
    last_received_at: str | None = None
    acquisition_session_id: str | None = None
    custom_profile_path: str | None = None
    failure: str | None = None
    schema_version: int = WITS0_RECOVERY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != WITS0_RECOVERY_SCHEMA_VERSION:
            raise ValueError("Unsupported WITS0 recovery manifest schema")
        if not self.run_id.strip() or not self.source_name.strip() or not self.raw_directory.strip():
            raise ValueError("Recovery manifest identifiers must not be empty")
        if isinstance(self.port, bool) or not 1 <= self.port <= 65_535:
            raise ValueError("Recovery manifest port is invalid")

    @property
    def unclean(self) -> bool:
        return not self.clean_shutdown and self.state in {
            Wits0RecoveryState.STARTING,
            Wits0RecoveryState.RUNNING,
            Wits0RecoveryState.FAILED,
        }


class Wits0RecoveryStore:
    """Atomic single-run recovery manifest stored beside the raw capture tree."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> Wits0RecoveryManifest | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return None
            return Wits0RecoveryManifest(
                run_id=str(payload["run_id"]),
                state=Wits0RecoveryState(str(payload["state"])),
                clean_shutdown=bool(payload["clean_shutdown"]),
                process_id=int(payload["process_id"]),
                started_at=str(payload["started_at"]),
                updated_at=str(payload["updated_at"]),
                mode=str(payload["mode"]),
                host=str(payload["host"]),
                port=int(payload["port"]),
                source_name=str(payload["source_name"]),
                raw_directory=str(payload["raw_directory"]),
                current_connection_id=_optional_str(payload.get("current_connection_id")),
                current_peer=_optional_str(payload.get("current_peer")),
                current_raw_file=_optional_str(payload.get("current_raw_file")),
                last_received_at=_optional_str(payload.get("last_received_at")),
                acquisition_session_id=_optional_str(payload.get("acquisition_session_id")),
                custom_profile_path=_optional_str(payload.get("custom_profile_path")),
                failure=_optional_str(payload.get("failure")),
                schema_version=int(payload.get("schema_version", 0)),
            )
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def save(self, manifest: Wits0RecoveryManifest) -> None:
        payload = json.dumps(
            asdict(manifest),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        _atomic_write_bytes(self.path, payload)

    def update(self, manifest: Wits0RecoveryManifest, **changes: object) -> Wits0RecoveryManifest:
        updated = replace(manifest, updated_at=_utc_now(), **changes)
        self.save(updated)
        return updated


@dataclass(frozen=True, slots=True)
class Wits0ConnectionJournalRecord:
    event: str
    occurred_at: str
    run_id: str
    connection_id: str | None
    mode: str
    endpoint: str
    peer: str | None
    reason: str | None = None
    raw_file: str | None = None
    bytes_received: int = 0
    frames_received: int = 0


class Wits0ConnectionJournal:
    """Append-only fsync-backed JSONL journal for connection lifecycle records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: Wits0ConnectionJournalRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            asdict(record),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())


@dataclass(frozen=True, slots=True)
class Wits0WorkspaceState:
    axis_mode: str = "auto"
    auto_follow: bool = True
    paused: bool = False
    follow_span: float = 600.0
    max_points: int = 2_000
    selected_curve_ids: tuple[str, ...] = ()
    history_start: float | None = None
    history_end: float | None = None
    acquisition_session_id: str | None = None
    schema_version: int = WITS0_WORKSPACE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != WITS0_WORKSPACE_SCHEMA_VERSION:
            raise ValueError("Unsupported WITS0 workspace schema")
        if self.axis_mode not in {"auto", "time", "depth"}:
            raise ValueError("Unsupported WITS0 workspace axis mode")
        if not isinstance(self.auto_follow, bool) or not isinstance(self.paused, bool):
            raise ValueError("Workspace flags must be booleans")
        if not 0.1 <= float(self.follow_span) <= 86_400.0:
            raise ValueError("follow_span is outside supported range")
        if isinstance(self.max_points, bool) or not 100 <= self.max_points <= 20_000:
            raise ValueError("max_points is outside supported range")
        if (self.history_start is None) != (self.history_end is None):
            raise ValueError("History range must contain both start and end")
        if (
            self.history_start is not None
            and self.history_end is not None
            and self.history_end <= self.history_start
        ):
            raise ValueError("History range end must be greater than start")


class _SettingsLike(Protocol):
    def value(self, key: str, default: object = None) -> object: ...
    def setValue(self, key: str, value: object) -> None: ...
    def sync(self) -> None: ...


class Wits0WorkspaceSettings:
    def __init__(self, settings: _SettingsLike, *, namespace: str = "wits0/workspace") -> None:
        self.settings = settings
        self.namespace = namespace.rstrip("/")

    def load(self, workspace_id: str) -> Wits0WorkspaceState:
        raw = self.settings.value(self._key(workspace_id), "")
        try:
            payload = json.loads(str(raw))
            if not isinstance(payload, dict):
                return Wits0WorkspaceState()
            curves = payload.get("selected_curve_ids", [])
            if not isinstance(curves, list) or not all(isinstance(item, str) for item in curves):
                return Wits0WorkspaceState()
            return Wits0WorkspaceState(
                axis_mode=str(payload.get("axis_mode", "auto")),
                auto_follow=payload.get("auto_follow", True),
                paused=payload.get("paused", False),
                follow_span=float(payload.get("follow_span", 600.0)),
                max_points=int(payload.get("max_points", 2_000)),
                selected_curve_ids=tuple(curves),
                history_start=(
                    float(payload["history_start"])
                    if payload.get("history_start") is not None
                    else None
                ),
                history_end=(
                    float(payload["history_end"])
                    if payload.get("history_end") is not None
                    else None
                ),
                acquisition_session_id=_optional_str(payload.get("acquisition_session_id")),
                schema_version=int(payload.get("schema_version", 0)),
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return Wits0WorkspaceState()

    def save(self, workspace_id: str, state: Wits0WorkspaceState) -> None:
        self.settings.setValue(
            self._key(workspace_id),
            json.dumps(asdict(state), ensure_ascii=False, sort_keys=True),
        )
        self.settings.sync()

    def _key(self, workspace_id: str) -> str:
        safe = "".join(character if character.isalnum() or character in "-_." else "_" for character in workspace_id)
        return f"{self.namespace}/{safe or 'default'}"


def _segment_related_paths(path: Path) -> tuple[Path, ...]:
    return (
        path,
        path.with_suffix(".chunks.jsonl"),
        path.with_suffix(".meta.json"),
    )


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
