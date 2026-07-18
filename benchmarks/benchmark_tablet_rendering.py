from __future__ import annotations

import argparse
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from geoworkbench.tablet.geometry_cache import CurveGeometryCache, CurveGeometryKey


@dataclass(frozen=True)
class Result:
    samples: int
    first_build_s: float
    cache_hit_s: float
    zoom_build_s: float
    rendered_points: int
    peak_preserved: bool


def run_case(samples: int, *, point_budget: int = 5000) -> Result:
    axis = np.linspace(0.0, 20_000.0, samples, dtype=np.float64)
    values = np.sin(axis / 30.0)
    peak_index = samples // 2
    values[peak_index] = 10_000.0
    cache = CurveGeometryCache(max_entries=16)

    full_key = CurveGeometryKey(
        curve_id="TG",
        axis_id="MD",
        values_revision=(id(values), values.size),
        axis_revision=(id(axis), axis.size),
        top=0.0,
        bottom=20_000.0,
        max_points=point_budget,
        positive_values_only=False,
    )
    started = perf_counter()
    full_values, _ = cache.get_or_build(full_key, axis, values)
    first_build = perf_counter() - started

    started = perf_counter()
    cache.get_or_build(full_key, axis, values)
    cache_hit = perf_counter() - started

    zoom_key = CurveGeometryKey(
        curve_id="TG",
        axis_id="MD",
        values_revision=(id(values), values.size),
        axis_revision=(id(axis), axis.size),
        top=9_950.0,
        bottom=10_050.0,
        max_points=point_budget,
        positive_values_only=False,
    )
    started = perf_counter()
    cache.get_or_build(zoom_key, axis, values)
    zoom_build = perf_counter() - started

    return Result(
        samples=samples,
        first_build_s=first_build,
        cache_hit_s=cache_hit,
        zoom_build_s=zoom_build,
        rendered_points=full_values.size,
        peak_preserved=float(np.max(full_values)) == 10_000.0,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--samples",
        type=int,
        nargs="*",
        default=[100_000, 1_000_000, 5_000_000],
    )
    args = parser.parse_args()
    for count in args.samples:
        result = run_case(count)
        print(
            f"samples={result.samples} rendered={result.rendered_points} "
            f"first={result.first_build_s:.6f}s hit={result.cache_hit_s:.6f}s "
            f"zoom={result.zoom_build_s:.6f}s peak={result.peak_preserved}"
        )


if __name__ == "__main__":
    main()
