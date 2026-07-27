from __future__ import annotations

from pathlib import Path

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
