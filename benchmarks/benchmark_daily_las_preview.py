"""Measure WELL-02 preview fingerprints without writing artifacts or source data.

Run: python -m benchmarks.benchmark_daily_las_preview
O(rows * curves) hashing; temporary array buffers must remain bounded as rows grow.
"""
from __future__ import annotations

import json
from statistics import median
from time import perf_counter
import tracemalloc

import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.daily_las_growth import dataset_append_state_sha256


def measure(rows: int) -> dict[str, int | float]:
    dataset = Dataset("benchmark", "Preview", DatasetKind.GTI, DepthDomain.MD,
                      np.arange(rows, dtype=np.float64) * 0.1)
    for index in range(7):
        key = f"C{index + 1}"
        dataset.curves[key] = CurveData(
            CurveMetadata(key, key, key, "%", None, dataset.dataset_id),
            np.arange(rows, dtype=np.float64) * (index + 1),
        )
    expected = dataset_append_state_sha256(dataset)
    elapsed = []
    tracemalloc.start()
    try:
        for _ in range(5):
            started = perf_counter()
            assert dataset_append_state_sha256(dataset) == expected
            elapsed.append(perf_counter() - started)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    # Measures extra allocations of the fingerprint, excluding input arrays.
    # This deliberately does not claim whole-process RSS or full append latency.
    if peak > 4 * 1024 * 1024:
        raise AssertionError(f"Preview hashing exceeded 4 MiB temporary budget: {peak}")
    return {"rows": rows, "curves": 7, "median_seconds": median(elapsed),
            "peak_traced_bytes": peak}


if __name__ == "__main__":
    print(json.dumps([measure(rows) for rows in (100_000, 1_000_000)], indent=2))
