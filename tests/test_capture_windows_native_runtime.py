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
    )
    assert actual == {
        "schema_version": 1,
        "source_commit": sha,
        "python_version": "3.11.9",
        "os": "Windows",
        "os_release": "2022Server",
        "machine": "AMD64",
        "qt_runtime_version": "6.8.3",
        "packages": {name: f"{name}-pinned" for name in NATIVE_PACKAGES},
    }
    assert requested == list(NATIVE_PACKAGES)
    assert not any("path" in key or "env" in key for key in actual)


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
