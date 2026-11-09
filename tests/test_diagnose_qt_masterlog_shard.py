from __future__ import annotations

import pytest

from scripts.run_tests import _FORCED_NATIVE_BATCH_FILES, _test_file_shards

from tools.diagnose_qt_masterlog_shard import (
    TARGET_FILE,
    debugger_replay_passed,
    select_target_group,
)


@pytest.mark.parametrize(
    ("status", "output", "expected"),
    (
        (0, "================= 330 passed in 11.35s =================", True),
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
        (0, "================= 329 passed, 1 warning in 11.35s =================", True),
        (0, "================= 3 passed, 1 error in 11.35s =================", False),
        (0, "================= 3 passed, 2 errors in 11.35s =================", False),
        (0, "================= 3 passed in 11.35s =================\nFatal Python error: access violation", False),
    ),
)
def test_cdb_exit_does_not_mask_incomplete_or_crashed_pytest(
    status: int, output: str, expected: bool
) -> None:
    assert debugger_replay_passed(status, output) is expected


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
        ("sequence", (("pytest", (
            "tests/test_gas_curve_rendering_continuity.py",
            "tests/test_gas_interval_gis_review_ui.py",
            "tests/test_gas_interval_gis_source_review_ui.py",
            "tests/test_gas_mixture_line_patterns.py",
            "tests/test_gas_mixture_output_language.py",
            "tests/test_gas_update_coverage.py",
        )), ("cdb", (TARGET_FILE,)))),
        ("both", (("pytest", (TARGET_FILE,)), ("pytest", (
            "tests/test_gas_curve_rendering_continuity.py",
            "tests/test_gas_interval_gis_review_ui.py",
            "tests/test_gas_interval_gis_source_review_ui.py",
            "tests/test_gas_mixture_line_patterns.py",
            "tests/test_gas_mixture_output_language.py",
            "tests/test_gas_update_coverage.py",
        )), ("cdb", (TARGET_FILE,)))),
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
