from __future__ import annotations

from pathlib import Path

import pytest

from scripts import run_tests

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_dev_dependencies_include_async_pytest_plugin() -> None:
    """Async ETP tests must be runnable in a clean editable installation."""

    assert '"pytest-asyncio>=0.23"' in _read("pyproject.toml")


def test_isolated_runner_explicitly_loads_async_plugin() -> None:
    """Disabling global plugin autoload must not disable project async tests."""

    source = _read("scripts/run_tests.py")
    assert 'PYTEST_DISABLE_PLUGIN_AUTOLOAD' in source
    assert '"pytest_asyncio.plugin"' in source


def test_testing_guide_uses_the_project_runner_for_full_gate() -> None:
    """The current guide must point to the runner that owns plugin isolation."""

    assert "python scripts/run_tests.py -p no:cacheprovider" in _read("docs/TESTING.md")


def test_headless_runner_only_suppresses_known_missing_desktop_dependencies() -> None:
    """Reduced CI must not hide arbitrary collection errors."""

    source = _read("scripts/run_headless_tests.py")
    assert 'OPTIONAL_DESKTOP_MODULES = frozenset({"PySide6", "pyqtgraph", "lasio"})' in source
    assert "Unexpected collection failures" in source
    assert "pytest_asyncio.plugin" in source


@pytest.mark.parametrize("status", [1, 0xC0000005, -1073741819])
def test_child_failure_reports_selector_and_preserves_exit_status(monkeypatch, capsys, status):
    from subprocess import CompletedProcess

    monkeypatch.setattr(
        run_tests.subprocess, "run", lambda *args, **kwargs: CompletedProcess([], status)
    )
    result = run_tests._run_child([], ["tests/example.py::test_case"], {})
    assert result == status
    error = capsys.readouterr().err
    assert f"exit={status}" in error
    assert f"0x{status & 0xFFFFFFFF:08X}" in error
    assert "tests/example.py::test_case" in error


def test_successful_child_does_not_report_failure(monkeypatch, capsys):
    from subprocess import CompletedProcess

    monkeypatch.setattr(
        run_tests.subprocess, "run", lambda *args, **kwargs: CompletedProcess([], 0)
    )
    assert run_tests._run_child([], ["tests/example.py::test_case"], {}) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "filename", ["test_session_safety.py", "test_masterlog_header_dialog.py",
                 "test_navigation_organization.py", "test_main_window_visible_depth_refresh.py"]
)
def test_native_dialog_cases_run_in_single_test_processes(filename: str) -> None:
    """Native-sensitive dialogs must run once each without a shared Qt heap."""

    path = Path("tests") / filename
    nodes = run_tests._top_level_test_nodes(path)

    assert path.as_posix() in run_tests._FORCED_NATIVE_BATCH_FILES
    assert path.as_posix() in run_tests._SINGLE_TEST_PROCESS_FILES
    batches = [
        selectors
        for batch_path, selectors in run_tests._heavy_test_batches((path,))
        if batch_path == path.as_posix()
    ]
    assert len(batches) == len(nodes)
    assert all(len(selectors) == 1 for selectors in batches)
    assert tuple(selector for batch in batches for selector in batch) == nodes
    assert run_tests._test_file_shards(1, (path,)) == ()
