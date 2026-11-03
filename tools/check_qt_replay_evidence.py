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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), str(path.name))
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
    if not isinstance(runtime.get("qt_runtime_version"), str) or not runtime["qt_runtime_version"]:
        raise ValueError("Missing Qt runtime version")
    packages = runtime.get("packages")
    if not isinstance(packages, dict) or any(
        not isinstance(packages.get(name), str) or not packages[name]
        for name in NATIVE_PACKAGES
    ):
        raise ValueError("Missing required native package versions")

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
            or not (directory / filename).is_file()
        ):
            raise ValueError(f"Replay child #{index + 1} does not match the trusted plan")

        status = entry["status"]
        exit_code, exit_hex = entry.get("exit_code"), entry.get("windows_exit_hex")
        if status in {"timeout", "launch_error"}:
            valid_exit = exit_code is None and exit_hex is None
        else:
            valid_exit = (
                _integer(exit_code)
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
