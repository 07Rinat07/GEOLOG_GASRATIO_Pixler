from __future__ import annotations

import logging
from pathlib import Path

import pytest

from geoworkbench.acquisition import (
    Wits0CaptureConfig,
    Wits0CaptureEngine,
    Wits0CaptureEvent,
    Wits0CaptureEventKind,
    Wits0CaptureState,
    Wits0ConnectionMode,
)
from geoworkbench.acquisition import wits0_observability


def _config(tmp_path: Path) -> Wits0CaptureConfig:
    return Wits0CaptureConfig(
        mode=Wits0ConnectionMode.TCP_CLIENT,
        host="192.168.0.100",
        port=2041,
        raw_directory=tmp_path,
        source_name="geoscape-halliburton",
    )


def test_transport_error_is_mirrored_to_application_log(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = Wits0CaptureEvent(
        kind=Wits0CaptureEventKind.ERROR,
        occurred_at="2026-09-15T00:00:00.000Z",
        message="Cannot connect to WITS endpoint: connection refused",
        state=Wits0CaptureState.RETRY_WAIT,
        reason="connection_refused",
    )

    with caplog.at_level(logging.INFO, logger="geoworkbench"):
        wits0_observability._log_capture_event(_config(tmp_path), event)

    record = caplog.records[-1]
    rendered = record.getMessage()
    assert record.levelno == logging.ERROR
    assert rendered.startswith("event=wits0.capture.error | ")
    assert 'endpoint="192.168.0.100:2041"' in rendered
    assert 'mode="tcp_client"' in rendered
    assert 'reason="connection_refused"' in rendered
    assert 'state="retry_wait"' in rendered
    assert 'source="geoscape-halliburton"' in rendered


def test_parser_diagnostic_is_logged_without_raw_payload_values(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = Wits0CaptureEvent(
        kind=Wits0CaptureEventKind.DIAGNOSTIC,
        occurred_at="2026-09-15T00:00:00.000Z",
        message=(
            "value_parse_error: invalid literal for int() with base 10: "
            "'SECRET-WITS-VALUE'"
        ),
        frame=b"&&0108SECRET-WITS-FRAME!!",
    )

    with caplog.at_level(logging.INFO, logger="geoworkbench"):
        wits0_observability._log_capture_event(_config(tmp_path), event)

    record = caplog.records[-1]
    rendered = record.getMessage()
    assert record.levelno == logging.WARNING
    assert rendered.startswith("event=wits0.capture.diagnostic | ")
    assert 'diagnostic_code="value_parse_error"' in rendered
    assert "SECRET-WITS-VALUE" not in rendered
    assert "SECRET-WITS-FRAME" not in rendered


def test_frame_events_are_not_written_to_shared_application_log(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = Wits0CaptureEvent(
        kind=Wits0CaptureEventKind.FRAME,
        occurred_at="2026-09-15T00:00:00.000Z",
        message="WITS0 frame parsed",
        frame=b"&&010812.3!!",
    )

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="geoworkbench"):
        wits0_observability._log_capture_event(_config(tmp_path), event)

    assert not any(
        record.getMessage().startswith("event=wits0.capture.")
        for record in caplog.records
    )


def test_logging_failure_never_drops_capture_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenLogger:
        def log(self, *_args: object, **_kwargs: object) -> None:
            raise OSError("simulated log failure")

    monkeypatch.setattr(wits0_observability, "_LOGGER", BrokenLogger())
    engine = Wits0CaptureEngine(_config(tmp_path))
    event = Wits0CaptureEvent(
        kind=Wits0CaptureEventKind.STATE,
        occurred_at="2026-09-15T00:00:00.000Z",
        message="Connecting",
        state=Wits0CaptureState.CONNECTING,
    )

    engine._emit(event)

    assert engine.drain_events(max_events=10) == (event,)
