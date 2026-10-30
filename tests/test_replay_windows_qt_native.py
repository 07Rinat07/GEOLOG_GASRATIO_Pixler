from __future__ import annotations

import json
import subprocess

import pytest

import tools.replay_windows_qt_native as replay_module
from tools.replay_windows_qt_native import (
    CHILD_TIMEOUT_SECONDS,
    MAX_REPETITIONS,
    SCENARIOS,
    execute_replay,
    replay_plan,
)


def test_replay_plan_is_bounded_and_only_uses_known_selectors() -> None:
    plan = replay_plan(2, "both")
    assert len(plan) == 14
    assert [part[1] for part in plan] == [
        "dataset-merge-undo",
        "tablet-rebuild",
        "track-x-scale",
        "normalized-gas-tablet",
        "lithology-undo",
        "header-curve-redo",
        "combined",
    ] * 2
    for i, (_, selector) in enumerate(SCENARIOS):
        assert plan[i][2] == (selector,)
    assert plan[6][2] == tuple(selector for _, selector in SCENARIOS)


@pytest.mark.parametrize("repetitions", [0, -1, 6, True, "2"])
def test_replay_plan_rejects_invalid_repetition_counts(repetitions) -> None:
    with pytest.raises(ValueError, match="repetitions"):
        replay_plan(repetitions, "isolated")


def test_track_x_scale_crash_selector_is_replayed_alone_and_in_sequence() -> None:
    selector = "tests/test_main_window.py::test_window_applies_selected_track_x_scale"
    assert SCENARIOS[2] == ("track-x-scale", selector)
    plan = replay_plan(1, "both")
    assert plan[2] == (1, "track-x-scale", (selector,))
    assert selector in plan[6][2]


def test_normalized_gas_tablet_crash_selector_is_replayed_alone_and_in_sequence() -> None:
    selector = (
        "tests/test_main_window_normalized_gas_tablet.py::"
        "test_show_normalized_gas_button_opens_tablet_and_adds_track"
    )
    assert SCENARIOS[3] == ("normalized-gas-tablet", selector)
    plan = replay_plan(1, "both")
    assert plan[3] == (1, "normalized-gas-tablet", (selector,))
    assert selector in plan[6][2]


def test_lithology_undo_native_crash_selector_is_replayed_alone_and_in_sequence() -> None:
    selector = "tests/test_main_window.py::test_window_global_undo_routes_lithology_edits"
    assert SCENARIOS[4] == ("lithology-undo", selector)
    plan = replay_plan(1, "both")
    assert plan[4] == (1, "lithology-undo", (selector,))
    assert selector in plan[6][2]


def test_header_redo_native_crash_replayed_alone_and_in_sequence() -> None:
    selector = (
        "tests/test_main_window.py::"
        "test_window_global_undo_routes_header_and_curve_edits_in_chronological_order"
    )
    assert SCENARIOS[5] == ("header-curve-redo", selector)
    plan = replay_plan(1, "both")
    assert plan[5] == (1, "header-curve-redo", (selector,))
    assert selector in plan[6][2]


def test_maximum_replay_budget_reserves_time_for_windows_setup_and_artifacts() -> None:
    plan = replay_plan(MAX_REPETITIONS, "both")
    assert len(plan) == 35
    assert len(plan) * CHILD_TIMEOUT_SECONDS <= 90 * 60
    assert plan[-1][1] == "combined"


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
    assert len(commands) == 7
    assert commands[0][0][:4] == (
        "python.exe",
        "scripts/run_tests.py",
        "-p",
        "no:cacheprovider",
    )
    assert commands[6][0][-6:] == tuple(selector for _, selector in SCENARIOS)
    assert all(call[1]["timeout"] == CHILD_TIMEOUT_SECONDS for call in commands)
    assert all(call[1]["check"] is False for call in commands)
    report = json.loads((tmp_path / "diagnostics" / "results.json").read_text("utf-8"))
    assert report["completed"] == report["expected"] == 7
    assert report["all_passed"] is False
    assert [item["status"] for item in report["results"]] == [
        "passed",
        "native_crash",
        "passed",
        "passed",
        "passed",
        "passed",
        "passed",
    ]
    assert report["results"][1]["windows_exit_hex"] == "0xC0000005"
    assert (tmp_path / "diagnostics" / "iteration-01-tablet-rebuild.txt").exists()


@pytest.mark.parametrize(
    ("exit_code", "expected_status", "expected_hex"),
    [
        (0xC0000005, "native_crash", "0xC0000005"),
        (-1073741819, "native_crash", "0xC0000005"),
        (0xC0000374, "native_crash", "0xC0000374"),
        (1, "failed", "0x00000001"),
        (5, "failed", "0x00000005"),
    ],
)
def test_replay_classifies_known_windows_native_codes_without_masking_failures(
    tmp_path, exit_code, expected_status, expected_hex
) -> None:
    def run(command, **kwargs):
        return subprocess.CompletedProcess(
            command, exit_code, stdout="synthetic child", stderr=""
        )

    assert not execute_replay(
        tmp_path, repetitions=1, mode="sequence", runner=run
    )
    report = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert report["completed"] == report["expected"] == 1
    assert report["all_passed"] is False
    result = report["results"][0]
    assert result["status"] == expected_status
    assert result["exit_code"] == exit_code
    assert result["windows_exit_hex"] == expected_hex
    assert (tmp_path / result["log_file"]).read_text(
        encoding="utf-8"
    ) == "synthetic child"


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
    assert len(calls) == 6
    assert report["results"][0]["status"] == "timeout"
    assert report["results"][0]["exit_code"] is None
    assert report["results"][1]["status"] == "passed"
    assert report["results"][2]["status"] == "passed"
    assert "partial output" in (tmp_path / "iteration-01-dataset-merge-undo.txt").read_text(
        "utf-8"
    )


def test_replay_child_launch_error_is_recorded_without_masking_other_results(
    tmp_path,
) -> None:
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise FileNotFoundError("synthetic missing Python executable")
        return subprocess.CompletedProcess(command, 0, stdout="passed", stderr="")

    assert not execute_replay(
        tmp_path,
        repetitions=1,
        mode="isolated",
        runner=run,
    )
    report = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert len(calls) == 6
    assert report["completed"] == report["expected"] == 6
    assert report["all_passed"] is False
    assert [item["status"] for item in report["results"]] == [
        "launch_error",
        "passed",
        "passed",
        "passed",
        "passed",
        "passed",
    ]
    first = report["results"][0]
    assert first["exit_code"] is None
    assert first["windows_exit_hex"] is None
    assert "FileNotFoundError" in (
        tmp_path / first["log_file"]
    ).read_text(encoding="utf-8")
    assert "synthetic missing Python executable" in (
        tmp_path / first["log_file"]
    ).read_text(encoding="utf-8")
    assert report["results"][1]["exit_code"] == 0


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
    assert len(snapshots) == 7
    assert [report["completed"] for report in snapshots] == [0, 1, 2, 3, 4, 5, 6]
    assert all(report["expected"] == 7 for report in snapshots)
    assert all(report["all_passed"] is False for report in snapshots)
    final = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert final["completed"] == final["expected"] == 7
    assert final["all_passed"] is True


def test_interruption_before_first_child_result_keeps_initial_failure_snapshot(tmp_path) -> None:
    calls = 0

    def interrupt(command, **kwargs):
        nonlocal calls
        calls += 1
        snapshot = json.loads((tmp_path / "results.json").read_text("utf-8"))
        assert snapshot["schema_version"] == 1
        assert snapshot["mode"] == "both"
        assert snapshot["repetitions"] == 1
        assert snapshot["completed"] == 0
        assert snapshot["expected"] == 7
        assert snapshot["results"] == []
        assert snapshot["all_passed"] is False
        raise RuntimeError("synthetic parent interruption before first result")

    with pytest.raises(RuntimeError, match="before first result"):
        execute_replay(tmp_path, repetitions=1, mode="both", runner=interrupt)

    assert calls == 1
    assert not list(tmp_path.glob("iteration-*.txt"))
    saved = json.loads((tmp_path / "results.json").read_text("utf-8"))
    assert saved["completed"] == 0
    assert saved["all_passed"] is False


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
    assert report["expected"] == 7
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
