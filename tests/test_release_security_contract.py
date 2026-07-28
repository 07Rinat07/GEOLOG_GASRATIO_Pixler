from __future__ import annotations

from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements" / "release.lock"
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"
SECURITY_GATE = ROOT / "tools" / "release_security_gate.py"

EXPECTED_RUNTIME_PACKAGES = {
    "colorama",
    "defusedxml",
    "et-xmlfile",
    "etpproto",
    "etptypes",
    "fastavro",
    "lasio",
    "numpy",
    "openpyxl",
    "pydantic",
    "pyqtgraph",
    "pyside6",
    "pyside6-addons",
    "pyside6-essentials",
    "shiboken6",
    "typing-extensions",
    "typingx",
    "tzdata",
    "websockets",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def test_security_dependencies_are_declared_separately() -> None:
    payload = tomllib.loads(_read(ROOT / "pyproject.toml"))
    security = payload["project"]["optional-dependencies"]["security"]
    assert any(item.startswith("pip-audit") for item in security)
    assert any(item.startswith("detect-secrets") for item in security)
    assert any(item.startswith("bandit") for item in security)


def test_release_lock_is_targeted_fully_pinned_and_hashed() -> None:
    text = _read(LOCK)
    assert "CPython 3.11" in text
    assert "Windows x86-64" in text

    requirement_starts = [
        line
        for line in text.splitlines()
        if line and not line.startswith(("#", " ", "-"))
    ]
    assert requirement_starts
    assert all("==" in line for line in requirement_starts)
    assert "--hash=sha256:" in text
    assert "-e " not in text
    assert "git+" not in text

    blocks = re.split(r"\n(?=[A-Za-z0-9_.-]+==)", text)
    requirements = [block for block in blocks if re.match(r"^[A-Za-z0-9_.-]+==", block)]
    assert requirements
    assert all("--hash=sha256:" in block for block in requirements)
    assert all(
        re.search(r"--hash=sha256:[0-9a-f]{64}(?:\s|$)", block)
        for block in requirements
    )

    names = {
        _normalized_name(block.split("==", 1)[0])
        for block in requirements
    }
    assert names == EXPECTED_RUNTIME_PACKAGES


def test_workflow_syncs_the_lock_and_uploads_both_artifact_groups() -> None:
    text = _read(WORKFLOW)
    assert text.count("runs-on: windows-latest") == 2
    assert text.count("uv pip sync requirements/release.lock") == 2
    assert text.count("--require-hashes") == 2
    assert "pip-audit==2.10.1" in text
    assert "detect-secrets==1.5.0" in text
    assert "bandit==1.9.4" in text
    assert "tools/release_security_gate.py" in text
    assert "build/ci-artifacts/quality" in text
    assert "build/ci-artifacts/security" in text
    assert text.count("actions/upload-artifact@") == 2
    assert "persist-credentials: false" in text


def test_security_gate_produces_required_machine_readable_reports() -> None:
    text = _read(SECURITY_GATE)
    for filename in (
        "dependency-audit.json",
        "sbom.cdx.json",
        "secret-scan.json",
        "bandit.json",
        "security-manifest.json",
    ):
        assert filename in text
    assert "--require-hashes" in text
    assert '"cyclonedx-json"' in text
    assert '"--all-files"' in text
