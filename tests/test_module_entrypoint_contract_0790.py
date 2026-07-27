from __future__ import annotations

import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_COMMAND = "python -m geoworkbench.app.main"
ENTRYPOINT_TARGET = "geoworkbench.app.main:main"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_main_module_has_python_m_execution_guard() -> None:
    """The documented module must call main() when executed with python -m."""

    source = _read("src/geoworkbench/app/main.py")
    tree = ast.parse(source)

    guards = [
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    ]
    assert guards, "geoworkbench.app.main has no __main__ guard"
    assert 'raise SystemExit(main())' in source


def test_pyproject_console_scripts_use_the_same_main_function() -> None:
    """Optional console scripts must resolve to the same callable as python -m."""

    text = _read("pyproject.toml")
    script_block = re.search(r"\[project\.scripts\](.*?)(?:\n\[|\Z)", text, re.S)
    assert script_block is not None
    targets = re.findall(r'=\s*"([^"]+)"', script_block.group(1))
    assert targets
    assert all(target == ENTRYPOINT_TARGET for target in targets)


def test_current_documentation_uses_canonical_module_command() -> None:
    """The startup instruction may not drift between the project guides."""

    documents = (
        "README.md",
        "docs/TESTING.md",
        "docs/ru/README.md",
        "docs/kk/README.md",
        "docs/en/README.md",
    )
    for relative in documents:
        assert CANONICAL_COMMAND in _read(relative), relative
