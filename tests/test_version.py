import re
from pathlib import Path

import geoworkbench

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def test_package_version_matches_project_metadata() -> None:
    """The runtime version must follow pyproject.toml instead of a stale literal."""

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = VERSION_RE.search(pyproject)

    assert match is not None
    assert geoworkbench.__version__ == match.group(1)
