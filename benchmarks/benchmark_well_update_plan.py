"""Synthetic WELL-02 review scaling; run as a module, no output files."""
from __future__ import annotations

import json
from time import perf_counter

import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.services.well_update_plan import analyze_well_numerical_update


def measure(rows: int) -> dict[str, int | float]:
    datasets = []
    for name in ("target", "source"):
        dataset = Dataset(name, name, DatasetKind.GTI, DepthDomain.MD,
                          np.arange(rows, dtype=np.float64))
        dataset.curves["ROP"] = CurveData(
            CurveMetadata(name + ":rop", "ROP", "ROP", "m/h", None, name),
            np.full(rows, np.nan if name == "target" else 0.0),
        )
        datasets.append(dataset)
    start = perf_counter()
    plan = analyze_well_numerical_update(
        *datasets, source_name="synthetic.las", source_sha256="a" * 64,
    )
    elapsed = perf_counter() - start
    assert plan.gaps_filled == rows and len(plan.changes) == 200
    assert plan.preview_truncated
    assert np.isnan(datasets[0].curves["ROP"].values).all()
    assert (datasets[1].curves["ROP"].values == 0).all()
    return {"rows": rows, "seconds": elapsed, "retained_diff_cells": len(plan.changes)}


if __name__ == "__main__":
    results = [measure(rows) for rows in (100_000, 1_000_000)]
    ratio = results[1]["seconds"] / results[0]["seconds"]
    print(json.dumps({"results": results, "scaling_ratio": ratio}, indent=2))
    if ratio > 15:
        raise AssertionError(f"Superlinear review scaling: {ratio:.2f}")
