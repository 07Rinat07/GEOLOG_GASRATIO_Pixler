from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

import numpy as np
from numpy.typing import NDArray

from geoworkbench.calculations.gas_ratio import calculate_conditioned_ratios


Array = NDArray[np.float64]
_COMPONENTS = ("C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5")
DEFAULT_DATASET_SIZES: tuple[int, ...] = (100_000, 1_000_000)
DEFAULT_REPEATS = 3
MIN_ROWS = 100
MIN_REPEATS = 3
BYTES_PER_MIB = 1024.0 * 1024.0
MAX_NORMALIZED_TIME_FACTOR = 2.0
MAX_NORMALIZED_RSS_FACTOR = 1.5


@dataclass(frozen=True, slots=True)
class BenchmarkBudget:
    max_median_seconds: float
    max_peak_rss_mib: float


# Initial cross-machine guardrails. The accepted measurements are documented in
# docs/PERFORMANCE.md; these limits are intentionally wider than the observed baseline so CI
# detects material regressions without turning runner jitter into a release blocker.
DEFAULT_BUDGETS: dict[int, BenchmarkBudget] = {
    100_000: BenchmarkBudget(max_median_seconds=5.0, max_peak_rss_mib=512.0),
    1_000_000: BenchmarkBudget(max_median_seconds=45.0, max_peak_rss_mib=1536.0),
}


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    rows: int
    components: int
    repeats: int
    best_seconds: float
    median_seconds: float
    rows_per_second: float
    peak_rss_mib: float
    interpolated_rows: int
    derived_curves: int
    samples_seconds: tuple[float, ...]

    @classmethod
    def from_json_mapping(cls, payload: dict[str, Any]) -> BenchmarkResult:
        return cls(
            rows=int(payload["rows"]),
            components=int(payload["components"]),
            repeats=int(payload["repeats"]),
            best_seconds=float(payload["best_seconds"]),
            median_seconds=float(payload["median_seconds"]),
            rows_per_second=float(payload["rows_per_second"]),
            peak_rss_mib=float(payload["peak_rss_mib"]),
            interpolated_rows=int(payload["interpolated_rows"]),
            derived_curves=int(payload["derived_curves"]),
            samples_seconds=tuple(float(value) for value in payload["samples_seconds"]),
        )


def make_deterministic_fixture(rows: int) -> tuple[Array, dict[str, Array]]:
    if rows < MIN_ROWS:
        raise ValueError(f"Benchmark requires at least {MIN_ROWS} rows")

    depth = np.arange(rows, dtype=np.float64) * 0.1
    components: dict[str, Array] = {}
    base = np.linspace(0.0, 40.0, rows, dtype=np.float64)
    for index, mnemonic in enumerate(_COMPONENTS, start=1):
        values = 5.0 * index + np.sin(base / index) * (0.5 + index / 10.0)
        # Normal sparse acquisition: two missing rows between measured rows.
        sparse = values.copy()
        sparse[np.arange(rows) % 3 != 0] = np.nan
        # Real long outage must remain a gap after conditioning.
        outage_start = rows // 2
        outage_stop = min(rows, outage_start + max(100, rows // 100))
        sparse[outage_start:outage_stop] = np.nan
        components[mnemonic] = sparse
    return depth, components


def validate_repeats(repeats: int) -> None:
    if repeats < MIN_REPEATS:
        raise ValueError(f"Benchmark requires at least {MIN_REPEATS} repetitions")


def _array_digest(values: Array) -> bytes:
    if not values.flags.c_contiguous:
        raise AssertionError("Benchmark fixture arrays must stay C-contiguous")
    return hashlib.sha256(memoryview(values).cast("B")).digest()


def _peak_rss_bytes() -> int:
    if os.name == "nt":
        return _windows_peak_rss_bytes()

    import resource

    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return peak
    return peak * 1024


def _windows_peak_rss_bytes() -> int:
    import ctypes
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    process = kernel32.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
        error_code = ctypes.get_last_error()
        raise OSError(error_code, "GetProcessMemoryInfo failed")
    return int(counters.PeakWorkingSetSize)


def run_benchmark_worker(rows: int, *, repeats: int) -> BenchmarkResult:
    validate_repeats(repeats)
    depth, components = make_deterministic_fixture(rows)
    depth_digest = _array_digest(depth)
    component_digests = {
        mnemonic: _array_digest(values) for mnemonic, values in components.items()
    }

    durations: list[float] = []
    last_result = None
    for _ in range(repeats):
        started = perf_counter()
        last_result = calculate_conditioned_ratios(depth, components)
        durations.append(perf_counter() - started)

    assert last_result is not None
    if _array_digest(depth) != depth_digest:
        raise AssertionError("Conditioning benchmark mutated the depth input")
    for mnemonic, expected_digest in component_digests.items():
        if _array_digest(components[mnemonic]) != expected_digest:
            raise AssertionError(f"Conditioning benchmark mutated source component {mnemonic}")

    total = last_result.curves["TG_CALC"].values
    if total.shape != depth.shape:
        raise AssertionError("Derived curve length differs from depth length")

    samples = tuple(durations)
    median_seconds = median(samples)
    interpolated_rows = sum(
        last_result.conditioned_components.interpolated_count(mnemonic)
        for mnemonic in _COMPONENTS
    )
    return BenchmarkResult(
        rows=rows,
        components=len(_COMPONENTS),
        repeats=repeats,
        best_seconds=min(samples),
        median_seconds=median_seconds,
        rows_per_second=rows / median_seconds,
        peak_rss_mib=_peak_rss_bytes() / BYTES_PER_MIB,
        interpolated_rows=interpolated_rows,
        derived_curves=len(last_result.curves),
        samples_seconds=samples,
    )


def run_isolated_benchmark(rows: int, *, repeats: int) -> BenchmarkResult:
    validate_repeats(repeats)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-rows",
        str(rows),
        "--repeats",
        str(repeats),
    ]
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip() or "unknown worker failure"
        raise RuntimeError(f"Benchmark worker failed for {rows:,} rows: {details}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Benchmark worker returned invalid JSON for {rows:,} rows: {completed.stdout!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Benchmark worker returned non-object JSON for {rows:,} rows")
    return BenchmarkResult.from_json_mapping(payload)


def evaluate_results(
    results: list[BenchmarkResult],
    *,
    budgets: dict[int, BenchmarkBudget] | None = None,
) -> tuple[str, ...]:
    active_budgets = DEFAULT_BUDGETS if budgets is None else budgets
    violations: list[str] = []

    for result in results:
        budget = active_budgets.get(result.rows)
        if budget is None:
            continue
        if result.median_seconds > budget.max_median_seconds:
            violations.append(
                f"{result.rows:,} rows median time {result.median_seconds:.3f}s exceeds "
                f"{budget.max_median_seconds:.3f}s"
            )
        if result.peak_rss_mib > budget.max_peak_rss_mib:
            violations.append(
                f"{result.rows:,} rows peak RSS {result.peak_rss_mib:.1f} MiB exceeds "
                f"{budget.max_peak_rss_mib:.1f} MiB"
            )

    ordered = sorted(results, key=lambda result: result.rows)
    for previous, current in zip(ordered[:-1], ordered[1:], strict=True):
        if current.rows <= previous.rows:
            continue
        size_ratio = current.rows / previous.rows
        time_ratio = current.median_seconds / previous.median_seconds
        rss_ratio = current.peak_rss_mib / previous.peak_rss_mib
        if time_ratio > size_ratio * MAX_NORMALIZED_TIME_FACTOR:
            violations.append(
                f"time scaling {previous.rows:,}->{current.rows:,} is {time_ratio:.2f}x for "
                f"{size_ratio:.2f}x rows"
            )
        if rss_ratio > size_ratio * MAX_NORMALIZED_RSS_FACTOR:
            violations.append(
                f"RSS scaling {previous.rows:,}->{current.rows:,} is {rss_ratio:.2f}x for "
                f"{size_ratio:.2f}x rows"
            )

    return tuple(violations)


def _scaling_payload(results: list[BenchmarkResult]) -> list[dict[str, float | int]]:
    ordered = sorted(results, key=lambda result: result.rows)
    scaling: list[dict[str, float | int]] = []
    for previous, current in zip(ordered[:-1], ordered[1:], strict=True):
        scaling.append(
            {
                "from_rows": previous.rows,
                "to_rows": current.rows,
                "size_ratio": current.rows / previous.rows,
                "time_ratio": current.median_seconds / previous.median_seconds,
                "rss_ratio": current.peak_rss_mib / previous.peak_rss_mib,
            }
        )
    return scaling


def _print_human(results: list[BenchmarkResult], violations: tuple[str, ...]) -> None:
    for result in results:
        print(
            f"rows={result.rows:,} components={result.components} repeats={result.repeats} "
            f"best={result.best_seconds:.6f}s median={result.median_seconds:.6f}s "
            f"rows/s={result.rows_per_second:,.0f} peak_rss={result.peak_rss_mib:.1f}MiB "
            f"interpolated={result.interpolated_rows:,} derived={result.derived_curves}"
        )
    for item in _scaling_payload(results):
        print(
            f"scaling {item['from_rows']:,}->{item['to_rows']:,}: "
            f"size={item['size_ratio']:.2f}x time={item['time_ratio']:.2f}x "
            f"rss={item['rss_ratio']:.2f}x"
        )
    if violations:
        print("Performance gate: FAIL")
        for violation in violations:
            print(f"- {violation}")
    else:
        print("Performance gate: PASS")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark conditioned C1-C5 and derived Gas Ratio calculations"
    )
    parser.add_argument("rows", nargs="*", type=int, default=list(DEFAULT_DATASET_SIZES))
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--no-enforce",
        action="store_true",
        help="report measurements without failing on performance guardrails",
    )
    parser.add_argument("--worker-rows", type=int, help=argparse.SUPPRESS)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        validate_repeats(args.repeats)
    except ValueError as exc:
        parser.error(str(exc))

    if args.worker_rows is not None:
        result = run_benchmark_worker(args.worker_rows, repeats=args.repeats)
        print(json.dumps(asdict(result), ensure_ascii=False))
        return 0

    if not args.rows:
        parser.error("at least one row count is required")
    if any(rows < MIN_ROWS for rows in args.rows):
        parser.error(f"each dataset must contain at least {MIN_ROWS} rows")
    if len(set(args.rows)) != len(args.rows):
        parser.error("dataset row counts must be unique")

    results = [run_isolated_benchmark(rows, repeats=args.repeats) for rows in args.rows]
    violations = evaluate_results(results)
    payload = {
        "schema_version": 1,
        "passed": not violations,
        "results": [asdict(result) for result in results],
        "scaling": _scaling_payload(results),
        "violations": list(violations),
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human(results, violations)

    return 0 if args.no_enforce or not violations else 2


if __name__ == "__main__":
    raise SystemExit(main())
