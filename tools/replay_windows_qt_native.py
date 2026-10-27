"""Manually replay known Windows native Qt crash selectors in fresh/paired processes.

No arbitrary selector or shell command can be provided by workflow inputs.
This tool does not change the mandatory Windows Release Gate.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any


SCENARIOS = (
    (
        "dataset-merge-undo",
        "tests/test_main_window.py::"
        "test_window_global_undo_routes_dataset_merge_and_keeps_local_action_domain_safe",
    ),
    (
        "tablet-rebuild",
        "tests/test_tablet_plot_close_order.py::"
        "test_repeated_tablet_rebuild_releases_detached_plots_before_replacement",
    ),
)
MODES = ("isolated", "sequence", "both")
MAX_REPETITIONS = 5
CHILD_TIMEOUT_SECONDS = 360  # 15 maximum children × 6 minutes = 90 minutes


def replay_plan(
    repetitions: int,
    mode: str,
) -> tuple[tuple[int, str, tuple[str, ...]], ...]:
    """Pair clean-process executions with a two-selector shared-process probe."""

    if not isinstance(repetitions, int) or isinstance(repetitions, bool):
        raise ValueError("repetitions must be an integer")
    if not 1 <= repetitions <= MAX_REPETITIONS:
        raise ValueError(f"repetitions must be between 1 and {MAX_REPETITIONS}")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")

    plan: list[tuple[int, str, tuple[str, ...]]] = []
    for iteration in range(1, repetitions + 1):
        if mode in ("isolated", "both"):
            for label, selector in SCENARIOS:
                plan.append((iteration, label, (selector,)))
        if mode in ("sequence", "both"):
            plan.append(
                (iteration, "combined", tuple(selector for _, selector in SCENARIOS))
            )
    return tuple(plan)


def _captured_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def _save_results_atomically(path: Path, report: dict[str, Any]) -> None:
    """Replace the snapshot only after a complete, flushed JSON write.

    An interrupted diagnostic must not truncate the previous valid results.
    The temporary file lives beside its destination for an atomic rename on
    Windows and is removed if writing or replacement fails.
    """

    pending: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".results-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            pending = Path(handle.name)
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, path)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)


def execute_replay(
    output_dir: Path,
    *,
    repetitions: int,
    mode: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    python_executable: str = sys.executable,
) -> bool:
    """Collect every result and report failure if any test or child process fails."""

    plan = replay_plan(repetitions, mode)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "results.json"
    results: list[dict[str, Any]] = []

    for iteration, label, selectors in plan:
        log_name = f"iteration-{iteration:02d}-{label}.txt"
        command = (
            python_executable,
            "scripts/run_tests.py",
            "-p",
            "no:cacheprovider",
            *selectors,
        )
        returncode: int | None
        timed_out = False
        try:
            completed = runner(
                command,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=CHILD_TIMEOUT_SECONDS,
                check=False,
            )
            returncode = int(completed.returncode)
            output = _captured_text(completed.stdout) + _captured_text(completed.stderr)
        except subprocess.TimeoutExpired as exc:
            returncode = None
            timed_out = True
            output = _captured_text(exc.stdout) + _captured_text(exc.stderr)
            output += f"\nChild exceeded {CHILD_TIMEOUT_SECONDS} seconds\n"

        (output_dir / log_name).write_text(output, encoding="utf-8")
        result = {
            "iteration": iteration,
            "scenario": label,
            "selectors": list(selectors),
            "status": "timeout" if timed_out else "passed" if returncode == 0 else "failed",
            "exit_code": returncode,
            "windows_exit_hex": (
                f"0x{returncode & 0xFFFFFFFF:08X}" if returncode is not None else None
            ),
            "log_file": log_name,
        }
        results.append(result)
        report = {
            "schema_version": 1,
            "mode": mode,
            "repetitions": repetitions,
            "all_passed": len(results) == len(plan) and all(
                item["status"] == "passed" for item in results
            ),
            "completed": len(results),
            "expected": len(plan),
            "results": results,
        }
        # Keep the last complete snapshot intact across interrupted writes.
        _save_results_atomically(report_path, report)
        print(
            f"Qt replay {iteration}/{repetitions} {label}: {result['status']} "
            f"({result['windows_exit_hex'] or 'timeout'})",
            flush=True,
        )
    return all(item["status"] == "passed" for item in results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay known Qt #544 Windows selectors")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--mode", choices=MODES, default="both")
    args = parser.parse_args()
    try:
        success = execute_replay(
            args.output_dir, repetitions=args.repetitions, mode=args.mode
        )
    except ValueError as exc:
        parser.error(str(exc))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
