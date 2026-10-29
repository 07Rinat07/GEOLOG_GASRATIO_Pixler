from __future__ import annotations

import json

import pytest

from tools.capture_windows_native_runtime import (
    NATIVE_PACKAGES,
    runtime_identity,
    write_snapshot,
)


def test_native_runtime_identity_records_only_versions_and_commit() -> None:
    requested = []
    def version(package: str) -> str:
        requested.append(package)
        return f"{package}-pinned"

    sha = "a" * 40
    actual = runtime_identity(
        sha,
        package_version=version,
        qt_version=lambda: "6.8.3",
        python_version="3.11.9",
        machine="AMD64",
        system="Windows",
        release="2022Server",
        qt_test_platform="offscreen",
    )
    assert actual == {
        "schema_version": 2,
        "source_commit": sha,
        "python_version": "3.11.9",
        "os": "Windows",
        "os_release": "2022Server",
        "machine": "AMD64",
        "qt_runtime_version": "6.8.3",
        "qt_test_platform": "offscreen",
        "packages": {name: f"{name}-pinned" for name in NATIVE_PACKAGES},
    }
    assert requested == list(NATIVE_PACKAGES)
    assert not any("path" in key or "env" in key for key in actual)


@pytest.mark.parametrize(
    ("platform_setting", "expected"),
    [
        ("offscreen", "offscreen"),
        ("windows", "windows"),
        ("minimal", "minimal"),
        ("", "other"),
        ("offscreen:/private/project-path", "other"),
        ("C:\\\\private\\\\test-runner", "other"),
    ],
)
def test_qt_test_platform_records_only_allowlisted_labels(
    platform_setting: str, expected: str,
) -> None:
    snapshot = runtime_identity(
        "b" * 40,
        package_version=lambda _package: "pinned",
        qt_version=lambda: "6.8.3",
        qt_test_platform=platform_setting,
    )
    assert snapshot["qt_test_platform"] == expected
    assert "/private" not in json.dumps(snapshot)
    assert "test-runner" not in json.dumps(snapshot)


def test_qt_test_platform_infers_test_runner_default_without_raw_env(
    monkeypatch,
) -> None:
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    kwargs = {
        "package_version": lambda _package: "pinned",
        "qt_version": lambda: "6.8.3",
    }
    default = runtime_identity("c" * 40, **kwargs)
    assert default["qt_test_platform"] == "offscreen"
    monkeypatch.setenv("QT_QPA_PLATFORM", "/home/private/qt/plugins")
    sanitized = runtime_identity("c" * 40, **kwargs)
    assert sanitized["qt_test_platform"] == "other"
    assert "/home/private" not in json.dumps(sanitized)


@pytest.mark.parametrize("sha", ["", "abc", "z" * 40, "A" * 40, "0" * 39])
def test_native_runtime_snapshot_rejects_invalid_commit_before_importing_qt(sha: str) -> None:
    def forbidden() -> str:
        raise AssertionError("Qt import must not be needed for invalid SHA")
    with pytest.raises(ValueError, match="40-character"):
        runtime_identity(sha, qt_version=forbidden)


def test_native_runtime_snapshot_writes_machine_readable_utf8(tmp_path) -> None:
    target = tmp_path / "quality" / "native-runtime.json"
    payload = {"source_commit": "a" * 40, "qt_runtime_version": "6.8.3"}
    write_snapshot(target, payload)
    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert target.read_bytes().endswith(b"\n")
