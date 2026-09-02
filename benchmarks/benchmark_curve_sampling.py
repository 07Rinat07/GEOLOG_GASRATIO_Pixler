from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
from time import perf_counter
from typing import Any

import numpy as np

from geoworkbench.tablet.geometry_cache import CurveGeometryCache, CurveGeometryKey


DEFAULT_SIZES = (1_000_000, 5_000_000, 10_000_000)
DEFAULT_MAX_POINTS = 4096
DEFAULT_CACHE_BYTES = 64 * 1024 * 1024


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


def _peak_rss_mib() -> float:
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            process, ctypes.byref(counters), counters.cb
        )
        if not ok:
            raise OSError("GetProcessMemoryInfo failed")
        return float(counters.PeakWorkingSetSize) / (1024.0 * 1024.0)

    peak = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return peak / (1024.0 * 1024.0)
    return peak / 1024.0


def _measure(rows: int, *, max_points: int, cache_bytes: int) -> dict[str, Any]:
    depth = np.linspace(0.0, 20_000.0, rows, dtype=np.float64)
    values = depth.copy()
    values /= 30.0
    np.sin(values, out=values)
    values[rows // 2] = 1000.0

    cache = CurveGeometryCache(max_entries=512, max_bytes=cache_bytes)
    full_key = _key(top=0.0, bottom=20_000.0, max_points=max_points)

    started = perf_counter()
    cold = cache.get_or_build(full_key, depth, values)
    cold_ms = (perf_counter() - started) * 1000.0

    started = perf_counter()
    hit = cache.get_or_build(full_key, depth, values)
    hit_ms = (perf_counter() - started) * 1000.0
    if hit is not cold:
        raise AssertionError("cache hit did not reuse the cached geometry")

    zoom_key = _key(top=9_000.0, bottom=11_000.0, max_points=max_points)
    started = perf_counter()
    zoom = cache.get_or_build(zoom_key, depth, values)
    zoom_ms = (perf_counter() - started) * 1000.0

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
        "peak_rss_mib": _peak_rss_mib(),
    }
    _enforce_structural_contract(result)
    return result


def _enforce_structural_contract(result: dict[str, Any]) -> None:
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


def _worker_command(rows: int, max_points: int, cache_bytes: int) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-rows",
        str(rows),
        "--max-points",
        str(max_points),
        "--cache-bytes",
        str(cache_bytes),
    ]


def _run_isolated(rows: int, *, max_points: int, cache_bytes: int) -> dict[str, Any]:
    completed = subprocess.run(
        _worker_command(rows, max_points, cache_bytes),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark revision-aware tablet geometry cache cold/hit/zoom paths."
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=_positive_int,
        default=list(DEFAULT_SIZES),
        help="input sample counts; default: 1M 5M 10M",
    )
    parser.add_argument("--max-points", type=_positive_int, default=DEFAULT_MAX_POINTS)
    parser.add_argument("--cache-bytes", type=_positive_int, default=DEFAULT_CACHE_BYTES)
    parser.add_argument("--worker-rows", type=_positive_int, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.worker_rows is not None:
        print(
            json.dumps(
                _measure(
                    args.worker_rows,
                    max_points=args.max_points,
                    cache_bytes=args.cache_bytes,
                ),
                sort_keys=True,
            )
        )
        return

    results = [
        _run_isolated(rows, max_points=args.max_points, cache_bytes=args.cache_bytes)
        for rows in args.sizes
    ]
    payload = {
        "contract": {
            "sizes": args.sizes,
            "max_points": args.max_points,
            "cache_max_bytes": args.cache_bytes,
            "timing_thresholds": None,
        },
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    for result in results:
        print(
            "rows={input_rows} cold={cold_ms:.3f}ms hit={hit_ms:.3f}ms "
            "zoom={zoom_ms:.3f}ms cache={cache_current_bytes}/{cache_max_bytes}B "
            "peak_rss={peak_rss_mib:.1f}MiB".format(**result)
        )


if __name__ == "__main__":
    main()
