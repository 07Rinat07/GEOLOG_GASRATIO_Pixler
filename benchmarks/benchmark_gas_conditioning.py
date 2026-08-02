from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from time import perf_counter

import numpy as np

from geoworkbench.calculations.gas_ratio import calculate_conditioned_ratios


_COMPONENTS = ("C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5")


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    rows: int
    components: int
    seconds: float
    rows_per_second: float
    interpolated_rows: int
    derived_curves: int


def _fixture(rows: int) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    if rows < 100:
        raise ValueError("Benchmark требует минимум 100 строк")
    depth = np.arange(rows, dtype=np.float64) * 0.1
    components: dict[str, np.ndarray] = {}
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


def run_benchmark(rows: int, *, repeats: int) -> BenchmarkResult:
    depth, components = _fixture(rows)
    source_snapshots = {name: values.copy() for name, values in components.items()}
    durations: list[float] = []
    last_result = None
    for _ in range(repeats):
        started = perf_counter()
        last_result = calculate_conditioned_ratios(depth, components)
        durations.append(perf_counter() - started)

    assert last_result is not None
    for mnemonic, source in source_snapshots.items():
        np.testing.assert_array_equal(components[mnemonic], source)
    total = last_result.curves["TG_CALC"].values
    if total.shape != depth.shape:
        raise AssertionError("Derived curve length differs from depth length")

    seconds = min(durations)
    interpolated_rows = sum(
        last_result.conditioned_components.interpolated_count(mnemonic)
        for mnemonic in _COMPONENTS
    )
    return BenchmarkResult(
        rows=rows,
        components=len(_COMPONENTS),
        seconds=seconds,
        rows_per_second=rows / seconds,
        interpolated_rows=interpolated_rows,
        derived_curves=len(last_result.curves),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark conditioned C1-C5 and derived Gas Ratio calculations"
    )
    parser.add_argument("rows", nargs="*", type=int, default=[100_000, 1_000_000])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats должен быть не меньше 1")

    results = [run_benchmark(rows, repeats=args.repeats) for rows in args.rows]
    scaling: list[dict[str, float | int]] = []
    for previous, current in zip(results[:-1], results[1:], strict=True):
        scaling.append(
            {
                "from_rows": previous.rows,
                "to_rows": current.rows,
                "size_ratio": current.rows / previous.rows,
                "time_ratio": current.seconds / previous.seconds,
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
                f"rows={result.rows:,} components={result.components} "
                f"seconds={result.seconds:.6f} rows/s={result.rows_per_second:,.0f} "
                f"interpolated={result.interpolated_rows:,} "
                f"derived={result.derived_curves}"
            )
        for item in scaling:
            print(
                f"scaling {item['from_rows']:,}->{item['to_rows']:,}: "
                f"size={item['size_ratio']:.2f}x time={item['time_ratio']:.2f}x"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
