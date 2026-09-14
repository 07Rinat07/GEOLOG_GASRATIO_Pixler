from __future__ import annotations

import json
import logging

from geoworkbench.acquisition.wits0_capture import (
    Wits0CaptureConfig,
    Wits0CaptureEngine as _BaseWits0CaptureEngine,
    Wits0CaptureEvent,
    Wits0CaptureEventKind,
)


_LOGGER = logging.getLogger("geoworkbench")
_LOGGED_EVENT_KINDS = frozenset(
    {
        Wits0CaptureEventKind.STATE,
        Wits0CaptureEventKind.CONNECTION,
        Wits0CaptureEventKind.DISCONNECTION,
        Wits0CaptureEventKind.DIAGNOSTIC,
        Wits0CaptureEventKind.WARNING,
        Wits0CaptureEventKind.ERROR,
        Wits0CaptureEventKind.DISK,
        Wits0CaptureEventKind.RETENTION,
        Wits0CaptureEventKind.RECOVERY,
    }
)
_LEVEL_BY_KIND = {
    Wits0CaptureEventKind.DIAGNOSTIC: logging.WARNING,
    Wits0CaptureEventKind.WARNING: logging.WARNING,
    Wits0CaptureEventKind.ERROR: logging.ERROR,
    Wits0CaptureEventKind.DISK: logging.WARNING,
}


def _safe_value(value: object) -> str:
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    return text if len(text) <= 600 else text[:597] + "..."


def _context_text(context: dict[str, object]) -> str:
    return " | " + " ".join(
        f"{key}={json.dumps(_safe_value(value), ensure_ascii=False)}"
        for key, value in sorted(context.items())
        if value is not None
    )


def _log_capture_event(config: Wits0CaptureConfig, event: Wits0CaptureEvent) -> None:
    if event.kind not in _LOGGED_EVENT_KINDS:
        return

    context: dict[str, object] = {
        "bytes_received": event.bytes_received or None,
        "connection_id": event.connection_id,
        "disk_free_bytes": event.disk_free_bytes,
        "endpoint": f"{config.host}:{config.port}",
        "frames_received": event.frames_received or None,
        "message": event.message or None,
        "mode": config.mode.value,
        "peer": event.peer,
        "reason": event.reason,
        "source": config.source_name,
        "state": event.state.value if event.state is not None else None,
    }
    level = _LEVEL_BY_KIND.get(event.kind, logging.INFO)
    _LOGGER.log(
        level,
        "event=wits0.capture.%s%s",
        event.kind.value,
        _context_text(context),
    )


class Wits0CaptureEngine(_BaseWits0CaptureEngine):
    """WITS0 capture engine with application-level transport diagnostics.

    Raw WITS frames and parsed values are deliberately excluded from the shared
    application log. Only connection, state, parser-diagnostic, warning/error,
    disk, retention and recovery events are mirrored. Logging failures never
    interrupt acquisition.
    """

    def _emit(self, event: Wits0CaptureEvent) -> None:
        super()._emit(event)
        try:
            _log_capture_event(self.config, event)
        except Exception:
            # Observability must never become part of the acquisition failure path.
            pass
