from __future__ import annotations

import argparse
import gc
import json
import tracemalloc
from dataclasses import asdict, dataclass
from time import perf_counter

import numpy as np

from geoworkbench.calculations.opus_gasomer import (
    calculate_opus_gasomer_batch,
    detect_opus_gasomer_intervals,
)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    rows: int
    batch_seconds: float
    detector_seconds: float
    batch_rows_per_second: float
    detector_rows_per_second: float
    batch_additional_peak_mib: float
    detector_additional_peak_mib: float
    detected_intervals: int


def _fixture(rows: int) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    if rows < 25_000:
        raise ValueError("Benchmark ОПУС Газомер требует минимум 25 000 строк")
    depth = np.arange(rows, dtype=np.float64) * 0.2
    total = np.full(rows, 0.01, dtype=np.float64)
    event_start = rows // 2
    event_stop = min(rows, event_start + 20)
    total[event_start:event_stop] = 0.20
    inputs = {
        "C1": total * (3.0 / 9.0),
        "C2": total * (2.0 / 9.0),
        "C3": total * (1.0 / 9.0),
        "C4": total * (1.0 / 9.0),
        "C5": total * (1.0 / 9.0),
        "TOTAL_GAS": total,
    }
    return depth, inputs


def _measure(operation):
    gc.collect()
    tracemalloc.start()
    started = perf_counter()
    result = operation()
    seconds = perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, seconds, peak / (1024.0 * 1024.0)


def run_benchmark(rows: int, *, repeats: int) -> BenchmarkResult:
    depth, inputs = _fixture(rows)
    lod = {name: 0.0 for name in ("C1", "C2", "C3", "C4", "C5")}
    lod["TOTAL_GAS"] = 0.001
    batch_samples: list[tuple[float, float]] = []
    detector_samples: list[tuple[float, float]] = []
    detected_intervals = 0
    for _ in range(repeats):
        batch, seconds, peak_mib = _measure(
            lambda: calculate_opus_gasomer_batch(inputs, units="%vol", lod=lod)
        )
        if batch.row_class_codes.shape != depth.shape:
            raise AssertionError("Batch result length differs from source depth")
        batch_samples.append((seconds, peak_mib))
        del batch

        detector, seconds, peak_mib = _measure(
            lambda: detect_opus_gasomer_intervals(
                depth,
                inputs["TOTAL_GAS"],
                unit="%vol",
                total_gas_lod=0.001,
            )
        )
        if detector.candidate_mask.shape != depth.shape:
            raise AssertionError("Detector result length differs from source depth")
        detected_intervals = len(detector.intervals)
        detector_samples.append((seconds, peak_mib))
        del detector

    batch_seconds, batch_peak = min(batch_samples, key=lambda item: item[0])
    detector_seconds, detector_peak = min(detector_samples, key=lambda item: item[0])
    return BenchmarkResult(
        rows=rows,
        batch_seconds=batch_seconds,
        detector_seconds=detector_seconds,
        batch_rows_per_second=rows / batch_seconds,
        detector_rows_per_second=rows / detector_seconds,
        batch_additional_peak_mib=batch_peak,
        detector_additional_peak_mib=detector_peak,
        detected_intervals=detected_intervals,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark synchronous OPUS Gasomer batch and local detector"
    )
    parser.add_argument("rows", nargs="*", type=int, default=[25_000, 100_000, 1_000_000])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats должен быть не меньше 1")

    results = [run_benchmark(rows, repeats=args.repeats) for rows in args.rows]
    scaling = []
    for previous, current in zip(results[:-1], results[1:], strict=True):
        scaling.append(
            {
                "from_rows": previous.rows,
                "to_rows": current.rows,
                "size_ratio": current.rows / previous.rows,
                "batch_time_ratio": current.batch_seconds / previous.batch_seconds,
                "detector_time_ratio": current.detector_seconds / previous.detector_seconds,
                "batch_peak_ratio": (
                    current.batch_additional_peak_mib / previous.batch_additional_peak_mib
                ),
                "detector_peak_ratio": (
                    current.detector_additional_peak_mib
                    / previous.detector_additional_peak_mib
                ),
            }
        )
    payload = {
        "results": [asdict(result) for result in results],
        "scaling": scaling,
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(
                f"rows={result.rows:,} batch={result.batch_seconds:.4f}s "
                f"detector={result.detector_seconds:.4f}s "
                f"batch_peak={result.batch_additional_peak_mib:.1f}MiB "
                f"detector_peak={result.detector_additional_peak_mib:.1f}MiB "
                f"intervals={result.detected_intervals}"
            )
        for item in scaling:
            print(
                f"scaling {item['from_rows']:,}->{item['to_rows']:,}: "
                f"size={item['size_ratio']:.2f}x "
                f"batch_time={item['batch_time_ratio']:.2f}x "
                f"detector_time={item['detector_time_ratio']:.2f}x "
                f"batch_peak={item['batch_peak_ratio']:.2f}x "
                f"detector_peak={item['detector_peak_ratio']:.2f}x"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
