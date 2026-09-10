"""Bounded numerical update staging at 100k/1M rows; no output files."""
from __future__ import annotations

import json
from time import perf_counter
import tracemalloc

import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.well_update_plan import analyze_well_numerical_update
from geoworkbench.services.well_update_apply import apply_well_numerical_update


def measure(rows: int) -> dict[str, int | float]:
    datasets = []
    for name in ("target", "source"):
        dataset = Dataset(name, name, DatasetKind.GTI, DepthDomain.MD, np.arange(rows, dtype=float))
        dataset.curves["ROP"] = CurveData(
            CurveMetadata(name + ":rop", "ROP", "ROP", "m/h", None, name),
            np.full(rows, np.nan if name == "target" else 0.0),
        )
        datasets.append(dataset)
    plan = analyze_well_numerical_update(*datasets, source_name="benchmark.las", source_sha256="a" * 64)
    tracemalloc.start()
    started = perf_counter()
    outcome = apply_well_numerical_update(
        *datasets, plan, source_name="benchmark.las", source_sha256="a" * 64,
        selected_changes=plan.changes,
    )
    seconds = perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(outcome.record.changes) == 200
    assert (datasets[0].curves["ROP"].values[:200] == 0).all()
    assert np.isnan(datasets[0].curves["ROP"].values[200:]).all()
    assert peak < 240 * rows + 8 * 1024 * 1024
    return {"rows": rows, "seconds": seconds, "peak_bytes": peak, "selected_cells": 200}


if __name__ == "__main__":
    print(json.dumps([measure(n) for n in (100_000, 1_000_000)], indent=2))
