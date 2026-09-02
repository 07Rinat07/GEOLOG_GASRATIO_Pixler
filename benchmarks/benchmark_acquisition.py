from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from geoworkbench.domain.acquisition import (
    AcquisitionCurveSchema,
    AcquisitionDataRowPayload,
    AcquisitionDatasetSchema,
    AcquisitionIndexSchema,
    AcquisitionRecord,
    AcquisitionRecordKind,
    AcquisitionSession,
)
from geoworkbench.domain.models import (
    CurveMetadata,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    Well,
)
from geoworkbench.services.acquisition import AcquisitionController


DEFAULT_DATASET_SIZES: tuple[int, ...] = (50_000, 100_000, 1_000_000)
BATCH_SIZE = 64
WINDOW_ROWS = 10_000
MAX_DOUBLE_SIZE_RATIO = 2.5
MAX_P95_BATCH_MS = 50.0
MAX_LAST_FIRST_WINDOW_RATIO = 2.0
BYTES_PER_MIB = 1024.0 * 1024.0


@dataclass(frozen=True, slots=True)
class AcquisitionBenchmarkResult:
    rows: int
    batch_size: int
    batches: int
    full_batches: int
    total_seconds: float
    rows_per_second: float
    p95_batch_ms: float
    first_window_ms: float
    last_window_ms: float
    last_first_ratio: float
    peak_rss_mib: float

    @classmethod
    def from_json_mapping(cls, payload: dict[str, Any]) -> AcquisitionBenchmarkResult:
        return cls(
            rows=int(payload["rows"]),
            batch_size=int(payload["batch_size"]),
            batches=int(payload["batches"]),
            full_batches=int(payload["full_batches"]),
            total_seconds=float(payload["total_seconds"]),
            rows_per_second=float(payload["rows_per_second"]),
            p95_batch_ms=float(payload["p95_batch_ms"]),
            first_window_ms=float(payload["first_window_ms"]),
            last_window_ms=float(payload["last_window_ms"]),
            last_first_ratio=float(payload["last_first_ratio"]),
            peak_rss_mib=float(payload["peak_rss_mib"]),
        )


def _schema() -> AcquisitionDatasetSchema:
    dataset_id = "benchmark-live-dataset"
    return AcquisitionDatasetSchema(
        dataset_id=dataset_id,
        name="Acquisition benchmark",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        indexes=(
            AcquisitionIndexSchema(
                index_id="depth-index",
                mnemonic="DEPT",
                index_type=IndexType.MD,
                role=IndexRole.DEPTH,
                unit="m",
            ),
        ),
        active_index_id="depth-index",
        curves=(
            AcquisitionCurveSchema(
                CurveMetadata(
                    curve_id="total-gas",
                    original_mnemonic="TG",
                    canonical_mnemonic="TG",
                    unit="%",
                    description="Total gas",
                    source_dataset_id=dataset_id,
                    provenance="benchmark:acquisition",
                )
            ),
            AcquisitionCurveSchema(
                CurveMetadata(
                    curve_id="rop",
                    original_mnemonic="ROP",
                    canonical_mnemonic="ROP",
                    unit="m/h",
                    description="Rate of penetration",
                    source_dataset_id=dataset_id,
                    provenance="benchmark:acquisition",
                )
            ),
        ),
    )


def _record(sequence: int) -> AcquisitionRecord:
    row = sequence - 1
    return AcquisitionRecord(
        record_id=f"benchmark-row-{sequence}",
        sequence=sequence,
        kind=AcquisitionRecordKind.DATA_ROW,
        payload=AcquisitionDataRowPayload(
            index_values=(("depth-index", 1_000.0 + row * 0.1),),
            curve_values=(
                ("total-gas", 0.5 + float(row % 200) / 100.0),
                ("rop", 8.0 + float(row % 40) / 10.0),
            ),
        ),
        received_at="2026-09-02T12:00:00+05:00",
        source="benchmark:perf03",
    )


def _nearest_rank_percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 < percentile <= 1.0:
        raise ValueError("percentile must be in (0, 1]")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _window_total_ms(batch_durations_ms: list[float]) -> tuple[float, float]:
    window_batches = math.ceil(WINDOW_ROWS / BATCH_SIZE)
    if len(batch_durations_ms) < window_batches * 2:
        raise ValueError(
            f"benchmark requires at least {window_batches * 2} full batches for first/last windows"
        )
    return (
        sum(batch_durations_ms[:window_batches]),
        sum(batch_durations_ms[-window_batches:]),
    )


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


def run_benchmark_worker(rows: int) -> AcquisitionBenchmarkResult:
    minimum_rows = WINDOW_ROWS * 2
    if rows < minimum_rows:
        raise ValueError(f"benchmark requires at least {minimum_rows:,} rows")

    well = Well("benchmark-well", "Acquisition benchmark")
    session = AcquisitionSession("benchmark-session", well.well_id, _schema())
    controller = AcquisitionController(
        well,
        session,
        max_pending_records=BATCH_SIZE,
    )

    batch_durations_ms: list[float] = []
    full_batch_durations_ms: list[float] = []
    next_sequence = 1
    while next_sequence <= rows:
        batch_count = min(BATCH_SIZE, rows - next_sequence + 1)
        records = tuple(
            _record(sequence)
            for sequence in range(next_sequence, next_sequence + batch_count)
        )
        started = perf_counter()
        controller.enqueue_many(records)
        applied = controller.drain(limit=batch_count, batch_size=BATCH_SIZE)
        elapsed_ms = (perf_counter() - started) * 1_000.0
        if len(applied) != batch_count:
            raise AssertionError("acquisition benchmark lost records during drain")
        batch_durations_ms.append(elapsed_ms)
        if batch_count == BATCH_SIZE:
            full_batch_durations_ms.append(elapsed_ms)
        next_sequence += batch_count

    if session.last_sequence != rows:
        raise AssertionError("acquisition benchmark session sequence diverged")
    if len(controller.dataset.depth) != rows:
        raise AssertionError("acquisition benchmark dataset row count diverged")

    first_window_ms, last_window_ms = _window_total_ms(full_batch_durations_ms)
    total_seconds = sum(batch_durations_ms) / 1_000.0
    return AcquisitionBenchmarkResult(
        rows=rows,
        batch_size=BATCH_SIZE,
        batches=len(batch_durations_ms),
        full_batches=len(full_batch_durations_ms),
        total_seconds=total_seconds,
        rows_per_second=rows / total_seconds,
        p95_batch_ms=_nearest_rank_percentile(full_batch_durations_ms, 0.95),
        first_window_ms=first_window_ms,
        last_window_ms=last_window_ms,
        last_first_ratio=last_window_ms / first_window_ms,
        peak_rss_mib=_peak_rss_bytes() / BYTES_PER_MIB,
    )


def run_isolated_benchmark(rows: int) -> AcquisitionBenchmarkResult:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-rows",
        str(rows),
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
        raise RuntimeError(f"Acquisition benchmark worker failed for {rows:,} rows: {details}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Acquisition benchmark worker returned invalid JSON for {rows:,} rows: "
            f"{completed.stdout!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Acquisition benchmark worker returned non-object JSON for {rows:,}")
    return AcquisitionBenchmarkResult.from_json_mapping(payload)


def evaluate_results(results: list[AcquisitionBenchmarkResult]) -> tuple[str, ...]:
    violations: list[str] = []
    ordered = sorted(results, key=lambda result: result.rows)

    for result in ordered:
        if result.batch_size != BATCH_SIZE:
            violations.append(
                f"{result.rows:,} rows used batch size {result.batch_size}, expected {BATCH_SIZE}"
            )
        if result.p95_batch_ms > MAX_P95_BATCH_MS:
            violations.append(
                f"{result.rows:,} rows p95 batch64 {result.p95_batch_ms:.3f} ms exceeds "
                f"{MAX_P95_BATCH_MS:.1f} ms"
            )
        if result.last_first_ratio > MAX_LAST_FIRST_WINDOW_RATIO:
            violations.append(
                f"{result.rows:,} rows last/first 10k ratio {result.last_first_ratio:.3f} "
                f"exceeds {MAX_LAST_FIRST_WINDOW_RATIO:.1f}"
            )

    by_rows = {result.rows: result for result in ordered}
    for smaller in ordered:
        larger = by_rows.get(smaller.rows * 2)
        if larger is None:
            continue
        ratio = larger.total_seconds / smaller.total_seconds
        if ratio > MAX_DOUBLE_SIZE_RATIO:
            violations.append(
                f"T({larger.rows:,})/T({smaller.rows:,})={ratio:.3f} exceeds "
                f"{MAX_DOUBLE_SIZE_RATIO:.1f}"
            )
    return tuple(violations)


def _parse_sizes(value: str) -> tuple[int, ...]:
    sizes = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not sizes:
        raise argparse.ArgumentTypeError("at least one benchmark size is required")
    if len(set(sizes)) != len(sizes):
        raise argparse.ArgumentTypeError("benchmark sizes must be unique")
    return sizes


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic acquisition PERF-03 benchmark")
    parser.add_argument(
        "--sizes",
        type=_parse_sizes,
        default=DEFAULT_DATASET_SIZES,
        help="comma-separated row counts; default: 50000,100000,1000000",
    )
    parser.add_argument("--no-enforce", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--worker-rows", type=int, default=None, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.worker_rows is not None:
        result = run_benchmark_worker(args.worker_rows)
        print(json.dumps(asdict(result), sort_keys=True))
        return 0

    results = [run_isolated_benchmark(rows) for rows in args.sizes]
    violations = () if args.no_enforce else evaluate_results(results)
    payload = {
        "contract": {
            "batch_size": BATCH_SIZE,
            "window_rows": WINDOW_ROWS,
            "max_double_size_ratio": MAX_DOUBLE_SIZE_RATIO,
            "max_p95_batch_ms": MAX_P95_BATCH_MS,
            "max_last_first_window_ratio": MAX_LAST_FIRST_WINDOW_RATIO,
        },
        "results": [asdict(result) for result in results],
        "violations": list(violations),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for result in results:
            print(
                f"{result.rows:>9,} rows | {result.rows_per_second:>10,.0f} rows/s | "
                f"p95 batch64 {result.p95_batch_ms:>7.3f} ms | "
                f"last/first {result.last_first_ratio:>5.2f} | "
                f"peak RSS {result.peak_rss_mib:>7.1f} MiB"
            )
        for violation in violations:
            print(f"FAIL: {violation}", file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
