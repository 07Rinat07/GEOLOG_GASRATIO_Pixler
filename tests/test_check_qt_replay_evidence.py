"""Headless checks of native Qt replay artifact identity and completeness."""
from __future__ import annotations

import json

import pytest

from tools import check_qt_replay_evidence
from tools.capture_windows_native_runtime import NATIVE_PACKAGES
from tools.replay_windows_qt_native import replay_plan


SHA = "a" * 40


def _write_artifacts(tmp_path, *, mode="sequence", repetitions=1, statuses=None, sha=SHA):
    plan = replay_plan(repetitions, mode)
    if statuses is None:
        statuses = ["passed"] * len(plan)
    records = []
    for iteration, label, selectors in plan[:len(statuses)]:
        status = statuses[len(records)]
        code = 0 if status == "passed" else 0xC0000005 if status == "native_crash" else None
        filename = f"iteration-{iteration:02d}-{label}.txt"
        (tmp_path / filename).write_text("synthetic test log", encoding="utf-8")
        records.append({
            "iteration": iteration, "scenario": label, "selectors": list(selectors),
            "status": status, "exit_code": code,
            "windows_exit_hex": f"0x{code & 0xFFFFFFFF:08X}" if code is not None else None,
            "log_file": filename,
        })
    full = len(records) == len(plan)
    (tmp_path / "results.json").write_text(json.dumps({
        "schema_version": 1, "mode": mode, "repetitions": repetitions,
        "completed": len(records), "expected": len(plan),
        "all_passed": full and all(s == "passed" for s in statuses),
        "results": records,
    }), encoding="utf-8")
    (tmp_path / "native-runtime.json").write_text(json.dumps({
        "schema_version": 2, "source_commit": sha, "os": "Windows",
        "qt_runtime_version": "6.8.0", "packages": {name: "1.0" for name in NATIVE_PACKAGES},
    }), encoding="utf-8")
    return plan


def test_complete_green_is_diagnostic_not_proof_of_fix(tmp_path):
    _write_artifacts(tmp_path)
    report, code = check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)
    assert code == 0
    assert report["diagnostic_status"] == "passed"
    assert report["qt_issue_544_resolved"] is False
    assert report["root_cause_confirmed"] is False


def test_native_crash_is_preserved_as_failure(tmp_path):
    _write_artifacts(tmp_path, statuses=["native_crash"])
    report, code = check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)
    assert code == 1
    assert report["native_crash_scenarios"] == ["combined"]
    assert report["failed_children"] == 1


def test_incomplete_progress_is_never_success(tmp_path):
    _write_artifacts(tmp_path, mode="both", statuses=["passed"])
    report, code = check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)
    assert code == 2
    assert report["diagnostic_status"] == "incomplete"
    assert report["completed"] == 1
    assert report["expected"] == 9


def test_wrong_runtime_sha_is_rejected(tmp_path):
    _write_artifacts(tmp_path, sha="b" * 40)
    with pytest.raises(ValueError, match="source commit"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)


def test_wrong_child_selector_is_rejected(tmp_path):
    _write_artifacts(tmp_path)
    path = tmp_path / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["results"][0]["selectors"] = ["tests/fake.py::fake"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="trusted plan"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)


def test_claiming_success_after_native_crash_is_rejected(tmp_path):
    _write_artifacts(tmp_path, statuses=["native_crash"])
    path = tmp_path / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["all_passed"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="all_passed"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)


def test_missing_log_and_nonwindows_runtime_are_rejected(tmp_path):
    _write_artifacts(tmp_path)
    (tmp_path / "iteration-01-combined.txt").unlink()
    with pytest.raises(ValueError, match="trusted plan"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)
    _write_artifacts(tmp_path)
    path = tmp_path / "native-runtime.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["os"] = "Linux"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Windows"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)


def test_cli_refuses_malformed_json_without_partial_report(tmp_path, capsys):
    (tmp_path / "native-runtime.json").write_text("{bad", encoding="utf-8")
    assert check_qt_replay_evidence.main([
        "--artifact-dir", str(tmp_path), "--commit", SHA,
    ]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "rejected" in captured.err


def test_inconsistent_native_crash_exit_code_is_rejected(tmp_path):
    _write_artifacts(tmp_path, statuses=["native_crash"])
    path = tmp_path / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["results"][0]["exit_code"] = 0
    data["results"][0]["windows_exit_hex"] = "0x00000000"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="inconsistent exit"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)


def test_boolean_schema_and_missing_versions_are_rejected(tmp_path):
    _write_artifacts(tmp_path)
    runtime_path = tmp_path / "native-runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["packages"].pop("shiboken6")
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    with pytest.raises(ValueError, match="package versions"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)
    _write_artifacts(tmp_path)
    path = tmp_path / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)


def test_malformed_unhashable_status_fails_closed(tmp_path):
    _write_artifacts(tmp_path)
    path = tmp_path / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["results"][0]["status"] = ["passed"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="trusted plan"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)


def test_redirected_results_json_is_rejected(tmp_path, monkeypatch):
    """A JSON link must not be followed even if its target looks valid."""
    import stat
    from pathlib import Path
    from types import SimpleNamespace

    _write_artifacts(tmp_path)
    real_lstat = Path.lstat
    target = tmp_path / "results.json"

    def pretend_json_symlink(path):
        if path == target:
            return SimpleNamespace(st_mode=stat.S_IFLNK | 0o777)
        return real_lstat(path)

    monkeypatch.setattr(Path, "lstat", pretend_json_symlink)
    with pytest.raises(ValueError, match="redirected replay artifact"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)


def test_reparse_log_file_is_rejected_on_any_runner(tmp_path, monkeypatch):
    """Model a Windows reparse-point file without requiring admin symlink rights."""
    import stat
    from pathlib import Path
    from types import SimpleNamespace

    _write_artifacts(tmp_path)
    real_lstat = Path.lstat
    target = tmp_path / "iteration-01-combined.txt"

    def pretend_windows_reparse(path):
        if path == target:
            return SimpleNamespace(
                st_mode=stat.S_IFREG | 0o644,
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
            )
        return real_lstat(path)

    monkeypatch.setattr(Path, "lstat", pretend_windows_reparse)
    with pytest.raises(ValueError, match="trusted plan"):
        check_qt_replay_evidence.verify_replay_evidence(tmp_path, SHA)


def test_missing_results_file_rejected_without_partial_report(tmp_path, capsys):
    _write_artifacts(tmp_path)
    (tmp_path / "results.json").unlink()
    assert check_qt_replay_evidence.main([
        "--artifact-dir", str(tmp_path), "--commit", SHA,
    ]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Missing or redirected" in captured.err
