"""Read-only verification of Windows Qt #544 manual replay evidence.

A completed successful replay is only a diagnostic observation, not proof
that the intermittent Qt crash is fixed. This module reads existing artifacts
without changing the replay workflow or modifying any files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import stat
import sys
from typing import Any

from tools.capture_windows_native_runtime import NATIVE_PACKAGES
from tools.replay_windows_qt_native import (
    WINDOWS_NATIVE_CRASH_CODES,
    replay_plan,
)


SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
STATUSES = frozenset({"passed", "native_crash", "timeout", "failed", "launch_error"})


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_plain_file(path: Path) -> bool:
    """Reject links and Windows reparse points rather than following them.

    These artifacts are independently downloaded evidence. A link is not
    equivalent to an ordinary file in the collected artifact directory.
    """
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and not (
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _has_diagnostic_content(path: Path) -> bool:
    """Reject blank logs without loading potentially large native traces."""
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8192), b""):
                if chunk.strip():
                    return True
    except OSError:
        return False
    return False


def _unique_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Do not let duplicate evidence fields silently override earlier values."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON evidence key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict[str, Any]:
    if not _is_plain_file(path):
        raise ValueError(f"Missing or redirected replay artifact: {path.name}")
    try:
        return _object(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_keys), str(path.name))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid JSON from {path.name}: {exc}") from exc


def verify_replay_evidence(directory: Path, commit: str) -> tuple[dict[str, Any], int]:
    """Validate the saved run against the trusted selector plan and runtime SHA.

    Return (report, exit_code): 0 complete/pass, 1 complete/failure,
    2 incomplete. Reject malformed/inconsistent evidence with ValueError.
    """
    if not isinstance(commit, str) or SHA_PATTERN.fullmatch(commit) is None:
        raise ValueError("commit must be a 40-character lowercase Git SHA")

    runtime = _read_json(directory / "native-runtime.json")
    if (
        not _integer(runtime.get("schema_version"))
        or runtime["schema_version"] != 2
        or runtime.get("source_commit") != commit
    ):
        raise ValueError("Runtime evidence schema or source commit does not match")
    if runtime.get("os") != "Windows":
        raise ValueError("Runtime evidence must come from Windows")
    if not isinstance(runtime.get("qt_runtime_version"), str) or not runtime["qt_runtime_version"].strip():
        raise ValueError("Missing Qt runtime version")
    # The capture schema records these platform details for native-triage
    # comparisons. Do not certify a replay whose Windows runtime is unknown.
    for field in ("python_version", "os_release", "machine"):
        value = runtime.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing Windows runtime identity: {field}")
    if runtime.get("qt_test_platform") not in ("offscreen", "windows", "minimal", "other"):
        raise ValueError("Missing or invalid normalized Qt test platform")
    packages = runtime.get("packages")
    if not isinstance(packages, dict) or any(
        not isinstance(packages.get(name), str) or not packages[name].strip()
        for name in NATIVE_PACKAGES
    ):
        raise ValueError("Missing required native package versions")
    # These four wheels share the Shiboken/PySide6 ABI. Keep their recorded
    # versions coherent before treating this run as comparable Qt evidence.
    binding_versions = {
        packages[name]
        for name in ("PySide6", "PySide6-Addons", "PySide6-Essentials", "shiboken6")
    }
    if len(binding_versions) != 1:
        raise ValueError("Inconsistent PySide6/shiboken6 binding versions")

    evidence = _read_json(directory / "results.json")
    if not _integer(evidence.get("schema_version")) or evidence["schema_version"] != 1:
        raise ValueError("Unsupported replay results schema")
    mode = evidence.get("mode")
    repetitions = evidence.get("repetitions")
    plan = replay_plan(repetitions, mode)
    completed, expected = evidence.get("completed"), evidence.get("expected")
    entries = evidence.get("results")
    if (
        not _integer(completed)
        or not _integer(expected)
        or not isinstance(entries, list)
        or expected != len(plan)
        or not 0 <= completed <= expected
        or len(entries) != completed
        or not isinstance(evidence.get("all_passed"), bool)
    ):
        raise ValueError("Inconsistent replay progress or expected count")

    crash_scenarios: list[str] = []
    failure_count = 0
    for index, row in enumerate(entries):
        entry = _object(row, f"results[{index}]")
        iteration, label, selectors = plan[index]
        filename = f"iteration-{iteration:02d}-{label}.txt"
        if (
            not _integer(entry.get("iteration"))
            or entry["iteration"] != iteration
            or entry.get("scenario") != label
            or entry.get("selectors") != list(selectors)
            or entry.get("log_file") != filename
            or not isinstance(entry.get("status"), str)
            or entry["status"] not in STATUSES
            or not _is_plain_file(directory / filename)
            or not _has_diagnostic_content(directory / filename)
        ):
            raise ValueError(f"Replay child #{index + 1} does not match the trusted plan")

        status = entry["status"]
        exit_code, exit_hex = entry.get("exit_code"), entry.get("windows_exit_hex")
        if status in {"timeout", "launch_error"}:
            valid_exit = exit_code is None and exit_hex is None
        else:
            valid_exit = (
                _integer(exit_code)
                # Windows subprocess return codes are signed or unsigned
                # 32-bit values. Do not silently truncate wider integers into
                # a known native-crash code when validating saved evidence.
                and -(1 << 31) <= exit_code <= (1 << 32) - 1
                and exit_hex == f"0x{exit_code & 0xFFFFFFFF:08X}"
                and (
                    (status == "passed" and exit_code == 0)
                    or (
                        status == "native_crash"
                        and (exit_code & 0xFFFFFFFF) in WINDOWS_NATIVE_CRASH_CODES
                    )
                    or (
                        status == "failed"
                        and exit_code != 0
                        and (exit_code & 0xFFFFFFFF) not in WINDOWS_NATIVE_CRASH_CODES
                    )
                )
            )
        if not valid_exit:
            raise ValueError(f"Replay child #{index + 1} has inconsistent exit evidence")
        if status != "passed":
            failure_count += 1
        if status == "native_crash":
            crash_scenarios.append(label)

    all_passed = completed == expected and failure_count == 0
    if evidence["all_passed"] is not all_passed:
        raise ValueError("Replay all_passed flag contradicts verified children")

    state = "incomplete" if completed < expected else "failed" if failure_count else "passed"
    summary: dict[str, Any] = {
        "source_commit": commit,
        "mode": mode,
        "repetitions": repetitions,
        "completed": completed,
        "expected": expected,
        "diagnostic_status": state,
        "failed_children": failure_count,
        "native_crash_scenarios": crash_scenarios,
        "root_cause_confirmed": False,
        "qt_issue_544_resolved": False,
    }
    return summary, {"passed": 0, "failed": 1, "incomplete": 2}[state]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Windows Qt #544 replay artifacts")
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--commit", required=True, help="Expected exact lowercase 40-character Git SHA")
    args = parser.parse_args(argv)
    try:
        report, code = verify_replay_evidence(args.artifact_dir, args.commit)
    except ValueError as exc:
        print(f"Replay evidence rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
