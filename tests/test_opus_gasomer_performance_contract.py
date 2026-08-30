from __future__ import annotations

from pathlib import Path


def test_opus_gasomer_keeps_a_bounded_benchmark_and_regular_axis_fast_path() -> None:
    benchmark = Path("benchmarks/benchmark_opus_gasomer.py")
    calculation = Path("src/geoworkbench/calculations/opus_gasomer.py")
    testing = Path("docs/TESTING.md").read_text(encoding="utf-8")

    assert benchmark.is_file()
    benchmark_source = benchmark.read_text(encoding="utf-8")
    calculation_source = calculation.read_text(encoding="utf-8")
    assert "25_000, 100_000, 1_000_000" in benchmark_source
    assert "tracemalloc.get_traced_memory()" in benchmark_source
    assert "_ROLLING_BLOCK_ELEMENTS" in calculation_source
    assert "sliding_window_view" in calculation_source
    assert "benchmarks/benchmark_opus_gasomer.py" in testing
