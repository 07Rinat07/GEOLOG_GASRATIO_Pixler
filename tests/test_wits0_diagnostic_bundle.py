from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from geoworkbench.services.application_logging import ApplicationLogManager


def test_diagnostic_bundle_includes_sanitized_wits0_journal_without_raw_frames(
    tmp_path: Path,
) -> None:
    app_data = tmp_path / "app-data"
    log_directory = app_data / "logs"
    source_directory = app_data / "raw" / "wits0" / "GeoScape-GSWITS-Halliburton"
    source_directory.mkdir(parents=True)

    raw_path = source_directory / "20260915-segment-000001.wits"
    raw_path.write_text("&&\n0108SECRET_RAW_VALUE\n!!\n", encoding="utf-8")
    journal_path = source_directory / "connections.jsonl"
    journal_path.write_text(
        json.dumps(
            {
                "event": "disconnected",
                "at": "2026-09-15T08:00:00Z",
                "run_id": "run-1",
                "connection_id": "connection-1",
                "peer": "192.168.0.100:2041",
                "reason": "timed out",
                "bytes_received": 128,
                "frames_received": 2,
                "parse_error_count": 0,
                "raw_file": r"C:\Users\SRR07\secret\20260915-segment-000001.wits",
                "raw_frame": "&&0108SECRET_RAW_VALUE!!",
                "unexpected_future_field": "must-not-leak",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    manager = ApplicationLogManager(log_directory, application_version="0.7.96")
    destination = tmp_path / "diagnostics.zip"
    try:
        result = manager.build_diagnostic_bundle(destination)
    finally:
        manager.close()

    with ZipFile(result.path) as archive:
        names = set(archive.namelist())
        journal_name = "attachments/wits0/connections-01.jsonl"
        assert journal_name in names
        assert not any(name.endswith(".wits") for name in names)
        payload = archive.read(journal_name).decode("utf-8")
        records = [json.loads(line) for line in payload.splitlines() if line]

    assert records == [
        {
            "event": "disconnected",
            "at": "2026-09-15T08:00:00Z",
            "run_id": "run-1",
            "connection_id": "connection-1",
            "peer": "192.168.0.100:2041",
            "reason": "timed out",
            "bytes_received": 128,
            "frames_received": 2,
            "parse_error_count": 0,
            "raw_file": "20260915-segment-000001.wits",
        }
    ]
    assert "SECRET_RAW_VALUE" not in payload
    assert "must-not-leak" not in payload
    assert "SRR07" not in payload


def test_diagnostic_bundle_without_wits0_journal_remains_valid(tmp_path: Path) -> None:
    manager = ApplicationLogManager(
        tmp_path / "app-data" / "logs",
        application_version="0.7.96",
    )
    destination = tmp_path / "diagnostics.zip"
    try:
        result = manager.build_diagnostic_bundle(destination)
    finally:
        manager.close()

    with ZipFile(result.path) as archive:
        names = set(archive.namelist())

    assert "system-report.json" in names
    assert "README.txt" in names
    assert not any(name.startswith("attachments/wits0/") for name in names)
