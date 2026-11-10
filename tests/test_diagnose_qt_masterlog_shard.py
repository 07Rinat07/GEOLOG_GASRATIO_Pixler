from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from scripts.run_tests import _FORCED_NATIVE_BATCH_FILES, _test_file_shards

from tools.diagnose_qt_masterlog_shard import (
    SEED_FILES,
    MAIN_FAILED_SHARD_FILES,
    RESAMPLE_UNDO_FILE,
    RESAMPLE_UNDO_NODE,
    TARGET_FILE,
    _cdb_startup_commands,
    _run_plain_target,
    debugger_replay_passed,
    select_target_group,
)


@pytest.mark.parametrize(
    ("status", "output", "expected"),
    (
        (0, "GEOLOG_CDB_ARMED\n================= 330 passed in 11.35s =================", True),
        (
            0,
            '0:000> sxe -c ".echo GEOLOG_CDB_NATIVE_EXCEPTION; .dump /m ..." 0xc0000374'
            '\n0:000> .echo GEOLOG_CDB_ARMED'
            '\nGEOLOG_CDB_ARMED'
            '\n================= 330 passed in 11.35s =================',
            True,
        ),
        (
            0,
            '0:000> .echo GEOLOG_CDB_ARMED'
            '\n================= 330 passed in 11.35s =================',
            False,
        ),
        (0, "================= 330 passed in 11.35s =================", False),
        (0, "GEOLOG_CDB_ARMED\nGEOLOG_CDB_NATIVE_EXCEPTION\n================= 330 passed in 11.35s =================", False),
        (1, "================= 330 passed in 11.35s =================", False),
        (0, "CDB captured an exception and quit", False),
        (0, "ExceptionCode: c0000005 (Access violation)", False),
        (0, "Windows fatal exception: code 0xc0000374", False),
        (0, "(123.4): Access violation (!!! second chance !!!)", False),
        (0, "================= 329 passed, 1 failed in 11.35s =================", False),
        (0, "tests/test_masterlog_columns_dialog.py::test_still_running PASSED", False),
        (0, "================= 329 passed, 1 skipped in 11.35s =================", False),
        (0, "================= 329 passed, 1 xfailed in 11.35s =================", False),
        (0, "================= 329 passed, 1 xpassed in 11.35s =================", False),
        (0, "================= 329 passed, 1 deselected in 11.35s =================", False),
        (0, "================= 329 passed, 1 rerun in 11.35s =================", False),
        (0, "GEOLOG_CDB_ARMED\n================= 329 passed, 1 warning in 11.35s =================", True),
        (0, "================= 3 passed, 1 error in 11.35s =================", False),
        (0, "================= 3 passed, 2 errors in 11.35s =================", False),
        (0, "================= 3 passed in 11.35s =================\nFatal Python error: access violation", False),
    ),
)
def test_cdb_exit_does_not_mask_incomplete_or_crashed_pytest(
    status: int, output: str, expected: bool
) -> None:
    assert debugger_replay_passed(status, output) is expected



def test_cdb_initializes_exception_filters_before_target_runs(tmp_path: Path) -> None:
    script = _cdb_startup_commands(tmp_path / "qt-native.dmp")
    lines = script.splitlines()
    assert lines[0].startswith('sxe -c "')
    assert lines[0].endswith(" 0xc0000374")
    assert lines[1].startswith('sxd -c2 "')
    assert lines[1].endswith(" av")
    assert lines[2].endswith(" 0xc0000409")
    assert all("GEOLOG_CDB_NATIVE_EXCEPTION" in line for line in lines[:3])
    assert all(".exr -1; r; kv; lm; .dump /m" in line for line in lines[:3])
    assert lines[-3:] == ["sxn ibp", ".echo GEOLOG_CDB_ARMED", "g"]


def test_cdb_launch_uses_startup_file_not_initial_dump(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tools import diagnose_qt_masterlog_shard as diagnostic

    sdk_root = tmp_path / "SDK"
    cdb = sdk_root / "Windows Kits/10/Debuggers/x64/cdb.exe"
    cdb.parent.mkdir(parents=True)
    cdb.touch()
    monkeypatch.setenv("ProgramFiles(x86)", str(sdk_root))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner"))
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        assert "-cf" in command
        assert "-o" in command  # Follow real python.exe spawned by venvlauncher.
        assert "-hd" in command  # Use normal Windows heap.
        assert "-g" not in command
        assert "-xd" not in command
        assert "-c" not in command
        startup_file = Path(command[command.index("-cf") + 1])
        assert startup_file.exists()
        assert startup_file.read_text(encoding="ascii").endswith("g\n")
        return subprocess.CompletedProcess(
            command, 0, "GEOLOG_CDB_ARMED\n================= 1 passed in 0.02s ================="
        )

    monkeypatch.setattr(diagnostic.subprocess, "run", fake_run)
    assert diagnostic._run_debugged_target((TARGET_FILE,), {}) == 0
    assert len(commands) == 1


def test_plain_control_uses_original_pytest_child_without_cdb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import diagnose_qt_masterlog_shard as diagnostic

    seen: list[tuple[tuple[str, ...], tuple[str, ...], dict[str, str]]] = []

    def fake_child(
        args: tuple[str, ...],
        selectors: tuple[str, ...],
        environment: dict[str, str],
    ) -> int:
        seen.append((args, selectors, environment))
        return 0

    monkeypatch.setattr(diagnostic, "_run_child", fake_child)
    env = {"QT_QPA_PLATFORM": "offscreen"}
    assert _run_plain_target(MAIN_FAILED_SHARD_FILES, env) == 0
    assert seen == [
        (("-s", "-p", "no:cacheprovider"), MAIN_FAILED_SHARD_FILES, env)
    ]


def test_resample_undo_selector_is_real_and_unambiguous() -> None:
    assert Path(RESAMPLE_UNDO_FILE).is_file()
    assert RESAMPLE_UNDO_NODE == (
        "tests/test_main_window.py::test_window_creates_and_undoes_resampled_copy"
    )


def test_failed_main_shard_manifest_preserves_original_sequence() -> None:
    assert MAIN_FAILED_SHARD_FILES[0] == "tests/test_las3_scalar_log_preview.py"
    assert MAIN_FAILED_SHARD_FILES[-1] == "tests/test_masterlog_control_layout.py"
    assert MAIN_FAILED_SHARD_FILES.count(TARGET_FILE) == 1
    assert len(MAIN_FAILED_SHARD_FILES) == 54


@pytest.mark.parametrize(
    ("shards", "expected"),
    (
        ((("tests/preceding.py", TARGET_FILE),), ("tests/preceding.py", TARGET_FILE)),
        ((("tests/preceding.py",),), (TARGET_FILE,)),
        ((), (TARGET_FILE,)),
    ),
)
def test_masterlog_diagnostic_targets_regular_or_native_isolated_file(
    shards: tuple[tuple[str, ...], ...], expected: tuple[str, ...]
) -> None:
    """PR #858 moves Masterlog out of regular shards; diagnostics must survive."""
    assert select_target_group(shards) == expected


@pytest.mark.parametrize(
    ("mode", "expected_calls"),
    (
        ("isolated", (("pytest", (TARGET_FILE,)),)),
        ("failing-shard", (("cdb", MAIN_FAILED_SHARD_FILES),)),
        ("plain-shard", (("plain", MAIN_FAILED_SHARD_FILES),)),
        (
            "resample-undo",
            (
                ("plain", (RESAMPLE_UNDO_NODE,)),
                ("cdb", (RESAMPLE_UNDO_NODE,)),
            ),
        ),
        ("sequence", (("pytest", SEED_FILES), ("cdb", (TARGET_FILE,)))),
        (
            "both",
            (
                ("pytest", (TARGET_FILE,)),
                ("pytest", SEED_FILES),
                ("cdb", (TARGET_FILE,)),
            ),
        ),
    ),
)
def test_masterlog_replay_modes_preserve_true_isolation(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_calls: tuple[tuple[str, tuple[str, ...]], ...],
) -> None:
    """An isolated replay must not inherit the seeded native Qt process."""
    from tools import diagnose_qt_masterlog_shard as diagnostic

    calls: list[tuple[str, tuple[str, ...]]] = []
    monkeypatch.setenv("GEOLOG_REPLAY_MODE", mode)
    monkeypatch.setenv("GEOLOG_REPLAY_REPETITIONS", "1")
    monkeypatch.setattr(diagnostic, "_test_file_shards", lambda _count: ())
    monkeypatch.setattr(diagnostic, "_configure_environment", lambda: None)

    def run_child(_args, selectors, _environment) -> int:
        calls.append(("pytest", tuple(selectors)))
        return 0

    def run_debugged(selectors, _environment) -> int:
        calls.append(("cdb", tuple(selectors)))
        return 0

    monkeypatch.setattr(diagnostic, "_run_child", run_child)
    monkeypatch.setattr(diagnostic, "_run_debugged_target", run_debugged)

    def run_plain(selectors, _environment) -> int:
        calls.append(("plain", tuple(selectors)))
        return 0

    monkeypatch.setattr(diagnostic, "_run_plain_target", run_plain)
    assert diagnostic.main() == 0
    assert calls == list(expected_calls)


def test_diagnostic_selector_tracks_real_windows_runner_partition() -> None:
    """The CDB target must exist in both pre- and post-isolation runner layouts."""
    shards = _test_file_shards(16)
    selected = select_target_group(shards)
    assert TARGET_FILE in selected
    regular_matches = [part for part in shards if TARGET_FILE in part]
    if TARGET_FILE in _FORCED_NATIVE_BATCH_FILES:
        assert not regular_matches
        assert selected == (TARGET_FILE,)
    else:
        assert len(regular_matches) == 1
        assert selected == regular_matches[0]
