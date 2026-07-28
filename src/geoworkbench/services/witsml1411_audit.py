from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Lock
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from geoworkbench.importers.witsml1411.models import Witsml1411AuditEvent


class Witsml1411AuditSink(Protocol):
    def record(self, event: Witsml1411AuditEvent) -> None: ...


@dataclass(slots=True)
class InMemoryWitsml1411AuditSink:
    events: list[Witsml1411AuditEvent]

    def __init__(self) -> None:
        self.events = []

    def record(self, event: Witsml1411AuditEvent) -> None:
        self.events.append(event)


class JsonlWitsml1411AuditSink:
    """Append-only, hash-chained audit log without request XML or credentials."""

    def __init__(self, path: str | Path, *, fsync: bool = True) -> None:
        self.path = Path(path)
        self.fsync = fsync
        self._lock = Lock()
        self._sequence, self._previous_hash = self._read_tail()

    def _read_tail(self) -> tuple[int, str]:
        if not self.path.exists():
            return 0, "0" * 64
        sequence = 0
        previous_hash = "0" * 64
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    entry_hash = str(payload.pop("entry_hash"))
                    current_sequence = int(payload["sequence"])
                    recorded_previous = str(payload["previous_hash"])
                    canonical = json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    calculated = sha256(canonical.encode("utf-8")).hexdigest()
                except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"WITSML SOAP audit log has an invalid record at line {line_number}"
                    ) from exc
                if current_sequence != sequence + 1:
                    raise ValueError(
                        f"WITSML SOAP audit sequence is broken at line {line_number}"
                    )
                if recorded_previous != previous_hash or entry_hash != calculated:
                    raise ValueError(
                        f"WITSML SOAP audit hash chain is broken at line {line_number}"
                    )
                sequence = current_sequence
                previous_hash = entry_hash
        return sequence, previous_hash

    def verify(self) -> tuple[int, str]:
        """Verify and return the current audit sequence and tail hash."""

        with self._lock:
            return self._read_tail()

    def record(self, event: Witsml1411AuditEvent) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._sequence += 1
            body = {
                "sequence": self._sequence,
                "previous_hash": self._previous_hash,
                "timestamp_utc": event.timestamp_utc.isoformat(),
                "request_id": event.request_id,
                "operation": event.operation,
                "endpoint": sanitize_endpoint(event.endpoint),
                "attempt": event.attempt,
                "outcome": event.outcome,
                "duration_seconds": round(event.duration_seconds, 6),
                "http_status": event.http_status,
                "witsml_result": event.witsml_result,
                "supplementary_message": _safe_message(event.supplementary_message),
                "object_type": event.object_type,
                "selection": dict(sorted(event.selection.items())),
            }
            canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            entry_hash = sha256(canonical.encode("utf-8")).hexdigest()
            body["entry_hash"] = entry_hash
            line = json.dumps(body, ensure_ascii=False, sort_keys=True) + "\n"
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                if self.fsync:
                    os.fsync(handle.fileno())
            self._previous_hash = entry_hash


def sanitize_endpoint(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def _safe_message(message: str | None) -> str | None:
    if message is None:
        return None
    # Supplementary messages can include server-side details. Keep a bounded,
    # single-line diagnostic and remove obvious authorization fragments.
    value = " ".join(message.replace("\x00", "").split())[:500]
    lowered = value.casefold()
    for marker in ("authorization:", "password=", "passwd=", "token="):
        position = lowered.find(marker)
        if position >= 0:
            value = value[:position] + marker + "<redacted>"
            break
    return value
