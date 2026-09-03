from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any

import numpy as np

from geoworkbench.tablet.geometry_cache import CurveGeometryCache, CurveGeometryKey


DEFAULT_SIZES = (1_000_000, 5_000_000, 10_000_000)
DEFAULT_MAX_POINTS = 4096
DEFAULT_CACHE_BYTES = 64 * 1024 * 1024
BYTES_PER_MIB = 1024.0 * 1024.0


def _key(*, top: float, bottom: float, max_points: int) -> CurveGeometryKey:
    return CurveGeometryKey(
        curve_id="GR",
        axis_id="depth",
        values_revision=1,
        axis_revision=1,
        top=top,
        bottom=bottom,
        max_points=max_points,
        positive_values_only=False,
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


def run_benchmark_worker(
    rows: int,
    *,
    max_points: int = DEFAULT_MAX_POINTS,
    cache_bytes: int = DEFAULT_CACHE_BYTES,
) -> dict[str, Any]:
    depth = np.linspace(0.0, 20_000.0, rows, dtype=np.float64)
    values = depth.copy()
    values /= 30.0
    np.sin(values, out=values)
    values[rows // 2] = 1000.0

    cache = CurveGeometryCache(max_entries=512, max_bytes=cache_bytes)
    full_key = _key(top=0.0, bottom=20_000.0, max_points=max_points)

    started = perf_counter()
    cold = cache.get_or_build(full_key, depth, values)
    cold_ms = (perf_counter() - started) * 1_000.0

    started = perf_counter()
    hit = cache.get_or_build(full_key, depth, values)
    hit_ms = (perf_counter() - started) * 1_000.0
    if hit is not cold:
        raise AssertionError("cache hit did not reuse the cached geometry")

    zoom_key = _key(top=9_000.0, bottom=11_000.0, max_points=max_points)
    started = perf_counter()
    zoom = cache.get_or_build(zoom_key, depth, values)
    zoom_ms = (perf_counter() - started) * 1_000.0

    stats = cache.stats()
    result: dict[str, Any] = {
        "input_rows": rows,
        "max_points": max_points,
        "cold_ms": cold_ms,
        "hit_ms": hit_ms,
        "zoom_ms": zoom_ms,
        "cold_output_rows": int(cold[0].size),
        "zoom_output_rows": int(zoom[0].size),
        "cache_entries": cache.entry_count,
        "cache_current_bytes": cache.current_bytes,
        "cache_max_bytes": cache.max_bytes,
        "cache_hits": stats.hits,
        "cache_misses": stats.misses,
        "cache_evictions": stats.evictions,
        "peak_rss_mib": _peak_rss_bytes() / BYTES_PER_MIB,
    }
    evaluate_result(result)
    return result


def evaluate_result(result: dict[str, Any]) -> None:
    if result["cache_current_bytes"] > result["cache_max_bytes"]:
        raise AssertionError("geometry cache exceeded its byte budget")
    if result["cache_hits"] != 1 or result["cache_misses"] != 2:
        raise AssertionError("cold/hit/zoom cache request contract changed")
    if result["cache_entries"] != 2:
        raise AssertionError("cold and zoom geometry must both remain cached")
    if result["cold_output_rows"] <= 0 or result["zoom_output_rows"] <= 0:
        raise AssertionError("sampling returned empty geometry")
    if result["peak_rss_mib"] <= 0:
        raise AssertionError("peak RSS measurement is unavailable")


def run_isolated_benchmark(
    rows: int,
    *,
    max_points: int = DEFAULT_MAX_POINTS,
    cache_bytes: int = DEFAULT_CACHE_BYTES,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-rows",
        str(rows),
        "--max-points",
        str(max_points),
        "--cache-bytes",
        str(cache_bytes),
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
        raise RuntimeError(f"Curve benchmark worker failed for {rows:,} rows: {details}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Curve benchmark worker returned invalid JSON for {rows:,} rows: "
            f"{completed.stdout!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Curve benchmark worker returned non-object JSON for {rows:,}")
    return payload


def _parse_sizes(value: str) -> tuple[int, ...]:
    sizes = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not sizes:
        raise argparse.ArgumentTypeError("at least one benchmark size is required")
    if len(set(sizes)) != len(sizes):
        raise argparse.ArgumentTypeError("benchmark sizes must be unique")
    if any(size < 1 for size in sizes):
        raise argparse.ArgumentTypeError("benchmark sizes must be positive")
    return sizes


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tablet geometry PERF-04 benchmark")
    parser.add_argument(
        "--sizes",
        type=_parse_sizes,
        default=DEFAULT_SIZES,
        help="comma-separated row counts; default: 1000000,5000000,10000000",
    )
    parser.add_argument("--max-points", type=_positive_int, default=DEFAULT_MAX_POINTS)
    parser.add_argument("--cache-bytes", type=_positive_int, default=DEFAULT_CACHE_BYTES)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--worker-rows", type=int, default=None, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.worker_rows is not None:
        if args.worker_rows < 1:
            raise ValueError("worker rows must be positive")
        result = run_benchmark_worker(
            args.worker_rows,
            max_points=args.max_points,
            cache_bytes=args.cache_bytes,
        )
        print(json.dumps(result, sort_keys=True))
        return 0

    results = [
        run_isolated_benchmark(
            rows,
            max_points=args.max_points,
            cache_bytes=args.cache_bytes,
        )
        for rows in args.sizes
    ]
    payload = {
        "contract": {
            "sizes": list(args.sizes),
            "max_points": args.max_points,
            "cache_max_bytes": args.cache_bytes,
            "timing_thresholds": None,
        },
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for result in results:
            print(
                "rows={input_rows:,} cold={cold_ms:.3f}ms hit={hit_ms:.3f}ms "
                "zoom={zoom_ms:.3f}ms cache={cache_current_bytes}/{cache_max_bytes}B "
                "peak_rss={peak_rss_mib:.1f}MiB".format(**result)
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
