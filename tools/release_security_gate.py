#!/usr/bin/env python3
"""Run the machine-readable security checks required for a release.

The command is intentionally a thin orchestrator around maintained security tools. Generated
reports are written below ``build/ci-artifacts`` by default, which is ignored by Git and uploaded
by CI. The script keeps running after an individual check fails so every available report and the
final manifest are preserved for review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "requirements" / "release.lock"
DEFAULT_ARTIFACT_DIR = ROOT / "build" / "ci-artifacts" / "security"


@dataclass(frozen=True)
class CheckResult:
    """Serializable result of one external security command."""

    name: str
    command: list[str]
    exit_code: int
    report: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


def _display_path(path: Path) -> str:
    """Return a stable project-relative path when possible."""

    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    name: str,
    command: Sequence[str],
    *,
    report: Path,
    cwd: Path = ROOT,
    stdout_to_report: bool = False,
) -> CheckResult:
    """Execute a command and retain stdout/stderr even when the command fails."""

    report.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env={**os.environ, "PYTHONUTF8": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if stdout_to_report:
        report.write_text(completed.stdout, encoding="utf-8")
    else:
        log_path = report.with_suffix(report.suffix + ".log")
        log_path.write_text(completed.stdout, encoding="utf-8")
    return CheckResult(
        name=name,
        command=list(command),
        exit_code=completed.returncode,
        report=_display_path(report),
    )


def _parse_secret_count(report: Path) -> int:
    payload = json.loads(report.read_text(encoding="utf-8"))
    results = payload.get("results", {})
    if not isinstance(results, dict):
        raise ValueError("detect-secrets report has no object-valued 'results' field")
    return sum(len(items) for items in results.values() if isinstance(items, list))


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    lock = args.lock.resolve()
    artifact_dir = args.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    if not lock.is_file():
        print(f"Release lock was not found: {lock}", file=sys.stderr)
        return 2

    dependency_report = artifact_dir / "dependency-audit.json"
    sbom_report = artifact_dir / "sbom.cdx.json"
    secret_report = artifact_dir / "secret-scan.json"
    bandit_report = artifact_dir / "bandit.json"

    checks = [
        _run(
            "dependency-audit",
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--require-hashes",
                "--no-deps",
                "--progress-spinner",
                "off",
                "--format",
                "json",
                "--output",
                str(dependency_report),
                "--requirement",
                str(lock),
            ],
            report=dependency_report,
        ),
        _run(
            "sbom",
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--require-hashes",
                "--no-deps",
                "--progress-spinner",
                "off",
                "--format",
                "cyclonedx-json",
                "--output",
                str(sbom_report),
                "--requirement",
                str(lock),
            ],
            report=sbom_report,
        ),
        _run(
            "secret-scan",
            [
                sys.executable,
                "-m",
                "detect_secrets",
                "scan",
                ".",
                "--all-files",
                "--exclude-files",
                r"(^|/)(\.git|build|dist|tmp|temp|\.cache|\.venv)(/|$)",
                "--exclude-files",
                r"(^|/)(project\.geolog\.json|.*\.geolog\.json\.assets)(/|$)",
                "--exclude-files",
                r"(^|/)requirements/release\.lock$",
                "--exclude-files",
                r"(^|/)(resources|src/geoworkbench/resources)/constructor_assets/",
                "--exclude-files",
                r"(^|/)vendor_reference/[^/]+/(derived|inventory)/",
                "--exclude-files",
                r"\.(bmp|png|jpe?g|gif|webp|ico|pdf|docx|xlsx|zip)$",
            ],
            report=secret_report,
            stdout_to_report=True,
        ),
        _run(
            "bandit",
            [
                sys.executable,
                "-m",
                "bandit",
                "--recursive",
                "src",
                "tools",
                "scripts",
                "--severity-level",
                "medium",
                "--confidence-level",
                "medium",
                "--format",
                "json",
                "--output",
                str(bandit_report),
            ],
            report=bandit_report,
        ),
    ]

    secret_count: int | None = None
    secret_error: str | None = None
    try:
        secret_count = _parse_secret_count(secret_report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        secret_error = str(exc)

    normalized_checks: list[dict[str, object]] = []
    failed = False
    for check in checks:
        payload = asdict(check)
        payload["passed"] = check.passed
        if check.name == "secret-scan":
            payload["finding_count"] = secret_count
            payload["report_error"] = secret_error
            if secret_count not in {0, None} or secret_error is not None:
                payload["passed"] = False
        if not payload["passed"]:
            failed = True
        normalized_checks.append(payload)

    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "lock_file": _display_path(lock),
        "lock_sha256": _sha256(lock),
        "checks": normalized_checks,
        "passed": not failed,
    }
    manifest_path = artifact_dir / "security-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    for check in normalized_checks:
        state = "PASS" if check["passed"] else "FAIL"
        print(f"[{state}] {check['name']}: {check['report']}")
    print(f"Manifest: {_display_path(manifest_path)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
