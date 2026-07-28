from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

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

    # The release lock targets CPython 3.11 on Windows x86-64.
    # websockets publishes both an sdist and platform wheels; uv selects
    # the cp311-win_amd64 wheel for this target, so its wheel hash must be
    # present and the source archive hash must not be used as the only hash.
    assert (
        "sha256:7421fad442de870a8cbf2287d1cad7e706ece0dbfeba5e911df132cbdc1cb56a"
        in text
    )
    assert (
        "sha256:db234eda965dcce15df96bb9709f587cd87d4d52aaf0e80e2f34ec04c7670c57"
        not in text
    )


def test_workflow_syncs_the_lock_and_uploads_three_artifact_groups() -> None:
    text = _read(WORKFLOW)
    assert text.count('version: "0.11.29"') == 3
    assert text.count(
        'astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b'
    ) == 3
    assert text.count("runs-on: windows-latest") == 3
    assert text.count("uv pip sync requirements/release.lock") == 3
    assert text.count("--require-hashes") == 3
    assert "pip-audit==2.10.1" in text
    assert "detect-secrets==1.5.0" in text
    gate = _read(ROOT / "tools" / "release_security_gate.py")
    assert "tests[\\\\/]golden_rendering" in gate
    assert "(^|[\\\\/])(\\.git|build" in gate
    assert "([\\\\/]|$)" in gate
    assert 'r"\\.(bmp|png|jpe?g|gif|webp|ico|pdf|docx|xlsx|zip|svg)$"' in gate
    assert 'uses:\\s*[^@\\s]+@[0-9a-f]{40}' in gate
    assert 'detect-secrets' in gate
    assert 'etp12\\\\?\\.secret' in gate
    assert 'witsml1411\\\\?\\.password' in gate
    assert 'hashed_secret' in gate
    assert "bandit==1.9.4" in text
    assert "tools/release_security_gate.py" in text
    assert "build/ci-artifacts/quality" in text
    assert "build/ci-artifacts/security" in text
    assert "build/ci-artifacts/windows-acceptance" in text
    assert "tools/windows_release_matrix.py" in text
    assert text.count("actions/upload-artifact@") == 3
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
    assert '"--no-verify"' in text


def test_secret_scan_keeps_structured_detectors_and_disables_entropy_noise() -> None:
    text = _read(ROOT / "tools" / "release_security_gate.py")
    assert '"--disable-plugin"' in text
    assert '"Base64HighEntropyString"' in text
    assert '"HexHighEntropyString"' in text
    assert 'finding_summaries' in text


def test_repository_constructor_thumbnails_are_not_ignored() -> None:
    ignore = _read(ROOT / ".gitignore")
    assert "!resources/constructor_assets/**/thumbnails/*.png" in ignore
    assert "!src/geoworkbench/resources/constructor_assets/**/thumbnails/*.png" in ignore

    package_root = ROOT / "src" / "geoworkbench" / "resources" / "constructor_assets"
    manifests = (
        package_root / "lithology" / "manifest.json",
        package_root / "symbols" / "manifest.json",
    )
    for manifest in manifests:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        root = manifest.parent.parent
        for asset in payload["assets"]:
            thumbnail = asset.get("thumbnail_path")
            if thumbnail:
                assert (root / thumbnail).is_file(), thumbnail


def test_secret_report_parser_returns_safe_metadata_only(tmp_path: Path) -> None:
    from tools.release_security_gate import _parse_secret_findings

    report = tmp_path / "secret-scan.json"
    report.write_text(
        json.dumps(
            {
                "results": {
                    "src/example.py": [
                        {
                            "type": "GitHub Token",
                            "line_number": 12,
                            "hashed_secret": "not-exposed",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    count, summaries = _parse_secret_findings(report)

    assert count == 1
    assert summaries == ("src/example.py:12: GitHub Token",)
    assert "not-exposed" not in summaries[0]


def test_repository_enforces_lf_for_platform_stable_text_contracts() -> None:
    attributes = _read(ROOT / ".gitattributes")
    assert "*.json text eol=lf" in attributes
    assert "*.svg text eol=lf" in attributes
    assert "*.png binary" in attributes


def test_windows_acceptance_uses_native_qt_on_windows_runner() -> None:
    workflow = _read(WORKFLOW)
    assert "runs-on: windows-latest" in workflow
    assert "--platform windows" in workflow
    assert "--platform offscreen" not in workflow


def test_secret_scan_exclusions_cover_only_known_false_positive_lines() -> None:
    import re

    from tools.release_security_gate import SECRET_SCAN_EXCLUDE_LINES

    pattern = re.compile(SECRET_SCAN_EXCLUDE_LINES)
    known_false_positives = (
        'detect-secrets==1.5.0',
        '"etp12.secret": "Password or bearer token",',
        '"witsml1411.password": "Password",',
        '"hashed_secret": "not-exposed",',
        'uses: actions/checkout@0123456789abcdef0123456789abcdef01234567',
    )
    assert all(pattern.search(line) for line in known_false_positives)
    api_key_line = "api_" + 'key = "ghp_example_real_token_shape"'
    password_line = "pass" + 'word = "operator-entered-value"'
    assert pattern.search(api_key_line) is None
    assert pattern.search(password_line) is None
