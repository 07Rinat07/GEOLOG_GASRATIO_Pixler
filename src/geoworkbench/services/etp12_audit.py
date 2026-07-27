from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from threading import RLock
from urllib.parse import urlsplit, urlunsplit

from geoworkbench.importers.etp12.models import Etp12AuditEvent


class JsonlEtp12AuditSink:
    """Append-only, hash-chained ETP audit log without payloads or credentials."""

    def __init__(self, path: Path, *, fsync: bool = True) -> None:
        self.path = Path(path)
        self.fsync = fsync
        self._lock = RLock()
        self._sequence, self._tail_hash = self._read_tail()

    def _read_tail(self) -> tuple[int, str]:
        if not self.path.exists():
            return 0, "0" * 64
        sequence = 0
        previous_hash = "0" * 64
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, raw in enumerate(handle, 1):
                if not raw.strip():
                    continue
                try:
                    payload = json.loads(raw)
                    entry_hash = str(payload.pop("entry_hash"))
                    current_sequence = int(payload["sequence"])
                    recorded_previous = str(payload["previous_hash"])
                    canonical = json.dumps(
                        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    )
                    calculated = sha256(canonical.encode("utf-8")).hexdigest()
                except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    raise ValueError(f"ETP audit log has an invalid record at line {line_number}") from exc
                if current_sequence != sequence + 1:
                    raise ValueError(f"ETP audit sequence is broken at line {line_number}")
                if recorded_previous != previous_hash or entry_hash != calculated:
                    raise ValueError(f"ETP audit hash chain is broken at line {line_number}")
                sequence = current_sequence
                previous_hash = entry_hash
        return sequence, previous_hash

    def verify(self) -> tuple[int, str]:
        with self._lock:
            return self._read_tail()

    def record(self, event: Etp12AuditEvent) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._sequence += 1
            body = {
                "sequence": self._sequence,
                "previous_hash": self._tail_hash,
                "timestamp_utc": event.timestamp_utc.isoformat(),
                "event": event.event,
                "endpoint": sanitize_etp_endpoint(event.endpoint),
                "outcome": event.outcome,
                "state": event.state.value,
                "attempt": event.attempt,
                "message_id": event.message_id,
                "correlation_id": event.correlation_id,
                "protocol": event.protocol,
                "message_type": event.message_type,
                "duration_seconds": (
                    round(event.duration_seconds, 6)
                    if event.duration_seconds is not None
                    else None
                ),
                "detail": _safe_detail(event.detail),
                "metadata": _safe_metadata(event.metadata),
            }
            canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            entry_hash = sha256(canonical.encode("utf-8")).hexdigest()
            body["entry_hash"] = entry_hash
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(body, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                if self.fsync:
                    os.fsync(handle.fileno())
            self._tail_hash = entry_hash


def sanitize_etp_endpoint(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def _safe_detail(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.replace("\x00", "").split())[:500]
    lowered = cleaned.casefold()
    for marker in ("authorization:", "password=", "passwd=", "token=", "bearer "):
        position = lowered.find(marker)
        if position >= 0:
            cleaned = cleaned[:position] + marker + "<redacted>"
            break
    return cleaned


def _safe_metadata(values) -> dict[str, object]:
    safe: dict[str, object] = {}
    for raw_key, raw_value in sorted(dict(values).items()):
        key = str(raw_key)[:100]
        lowered = key.casefold()
        if any(token in lowered for token in ("password", "secret", "token", "authorization")):
            safe[key] = "<redacted>"
        elif isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            safe[key] = str(raw_value)[:500] if isinstance(raw_value, str) else raw_value
        else:
            safe[key] = str(raw_value)[:500]
    return safe
