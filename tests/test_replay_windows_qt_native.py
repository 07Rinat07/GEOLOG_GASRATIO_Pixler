from __future__ import annotations

import json
import subprocess

import pytest

import tools.replay_windows_qt_native as replay_module
from tools.replay_windows_qt_native import (
    CHILD_TIMEOUT_SECONDS,
    SCENARIOS,
    execute_replay,
    replay_plan,
)


def test_replay_plan_is_bounded_and_only_uses_known_selectors() -> None:
    plan = replay_plan(2, "both")
    assert len(plan) == 6
    assert [part[1] for part in plan] == [
        "dataset-merge-undo",
        "tablet-rebuild",
        "combined",
    ] * 2
    assert plan[0][2] == (SCENARIOS[0][1],)
    assert plan[1][2] == (SCENARIOS[1][1],)
    assert plan[2][2] == tuple(selector for _, selector in SCENARIOS)


@pytest.mark.parametrize("repetitions", [0, -1, 6, True, "2"])
def test_replay_plan_rejects_invalid_repetition_counts(repetitions) -> None:
    with pytest.raises(ValueError, match="repetitions"):
        replay_plan(repetitions, "isolated")


def test_replay_plan_rejects_arbitrary_scenarios() -> None:
    with pytest.raises(ValueError, match="mode"):
        replay_plan(1, "external-command")


def test_replay_collects_all_child_failures_without_masking_windows_crash(tmp_path) -> None:
    commands = []
    def run(command, **kwargs):
        commands.append((command, kwargs))
        status = 3221225477 if len(commands) == 2 else 0
        return subprocess.CompletedProcess(command, status, stdout="synthetic run\n", stderr="")

    success = execute_replay(
        tmp_path / "diagnostics",
        repetitions=1,
        mode="both",
        runner=run,
        python_executable="python.exe",
    )

    assert success is False
    assert len(commands) == 3
    assert commands[0][0][:4] == (
        "python.exe",
        "scripts/run_tests.py",
        "-p",
        "no:cacheprovider",
    )
    assert commands[2][0][-2:] == tuple(selector for _, selector in SCENARIOS)
    assert all(call[1]["timeout"] == CHILD_TIMEOUT_SECONDS for call in commands)
    assert all(call[1]["check"] is False for call in commands)
    report = json.loads((tmp_path / "diagnostics" / "results.json").read_text("utf-8"))
    assert report["completed"] == report["expected"] == 3
    assert report["all_passed"] is False
    assert [item["status"] for item in report["results"]] == [
        "passed",
        "failed",
        "passed",
    ]
    assert report["results"][1]["windows_exit_hex"] == "0xC0000005"
    assert (tmp_path / "diagnostics" / "iteration-01-tablet-rebuild.txt").exists()


def test_replay_timeout_is_reported_as_failure_and_other_runs_continue(tmp_path) -> None:
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(command, CHILD_TIMEOUT_SECONDS, output=b"partial output")
        return subprocess.CompletedProcess(command, 0, stdout="passed", stderr="")

    assert not execute_replay(
        tmp_path, repetitions=1, mode="isolated", runner=run
    )
    report = json.loads((tmp_path / "results.json").read_text("utf-8"))
    assert len(calls) == 2
    assert report["results"][0]["status"] == "timeout"
    assert report["results"][0]["exit_code"] is None
    assert report["results"][1]["status"] == "passed"
    assert "partial output" in (tmp_path / "iteration-01-dataset-merge-undo.txt").read_text(
        "utf-8"
    )


def test_replay_success_returns_success_and_summary(tmp_path) -> None:
    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    assert execute_replay(tmp_path, repetitions=1, mode="sequence", runner=run)
    report = json.loads((tmp_path / "results.json").read_text("utf-8"))
    assert report["all_passed"] is True
    assert report["completed"] == report["expected"] == 1



def test_partial_replay_never_reports_success_while_children_remain(tmp_path) -> None:
    snapshots: list[dict] = []

    def run(command, **kwargs):
        path = tmp_path / "results.json"
        if path.exists():
            snapshots.append(json.loads(path.read_text(encoding="utf-8")))
        return subprocess.CompletedProcess(command, 0, stdout="passed", stderr="")

    assert execute_replay(tmp_path, repetitions=1, mode="both", runner=run)
    assert len(snapshots) == 2
    assert [report["completed"] for report in snapshots] == [1, 2]
    assert all(report["expected"] == 3 for report in snapshots)
    assert all(report["all_passed"] is False for report in snapshots)
    final = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert final["completed"] == final["expected"] == 3
    assert final["all_passed"] is True


def test_interrupted_replay_keeps_partial_report_failed(tmp_path) -> None:
    calls = 0

    def run(command, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic runner interruption")
        return subprocess.CompletedProcess(command, 0, stdout="passed", stderr="")

    with pytest.raises(RuntimeError, match="synthetic runner interruption"):
        execute_replay(tmp_path, repetitions=1, mode="both", runner=run)
    report = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert report["completed"] == 1
    assert report["expected"] == 3
    assert report["all_passed"] is False


def test_atomic_results_snapshot_replaces_complete_json(tmp_path) -> None:
    report_path = tmp_path / "results.json"
    report_path.write_text('{"previous": true}\n', encoding="utf-8")

    replay_module._save_results_atomically(
        report_path, {"completed": 2, "expected": 3, "all_passed": False}
    )

    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "completed": 2,
        "expected": 3,
        "all_passed": False,
    }
    assert list(tmp_path.glob(".results-*.tmp")) == []


def test_atomic_result_replace_failure_preserves_last_complete_snapshot(
    tmp_path, monkeypatch
) -> None:
    report_path = tmp_path / "results.json"
    previous = '{"completed": 1, "expected": 3, "all_passed": false}\n'
    report_path.write_text(previous, encoding="utf-8")

    def reject_replace(source, destination) -> None:
        assert destination == report_path
        assert source != report_path
        assert report_path.read_text(encoding="utf-8") == previous
        raise OSError("synthetic Windows file replace failure")

    monkeypatch.setattr(replay_module.os, "replace", reject_replace)
    with pytest.raises(OSError, match="synthetic Windows file replace failure"):
        replay_module._save_results_atomically(
            report_path, {"completed": 2, "expected": 3, "all_passed": False}
        )

    assert report_path.read_text(encoding="utf-8") == previous
    assert list(tmp_path.glob(".results-*.tmp")) == []
