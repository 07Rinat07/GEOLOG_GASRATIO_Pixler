from __future__ import annotations

from dataclasses import replace

import pytest

from benchmarks import benchmark_acquisition as benchmark


def _result(
    rows: int,
    *,
    total_seconds: float,
    p95_batch_ms: float = 10.0,
    last_first_ratio: float = 1.1,
) -> benchmark.AcquisitionBenchmarkResult:
    return benchmark.AcquisitionBenchmarkResult(
        rows=rows,
        batch_size=benchmark.BATCH_SIZE,
        batches=rows // benchmark.BATCH_SIZE + 1,
        full_batches=rows // benchmark.BATCH_SIZE,
        total_seconds=total_seconds,
        rows_per_second=rows / total_seconds,
        p95_batch_ms=p95_batch_ms,
        first_window_ms=1_000.0,
        last_window_ms=1_000.0 * last_first_ratio,
        last_first_ratio=last_first_ratio,
        peak_rss_mib=256.0,
    )


def test_nearest_rank_percentile_uses_observed_batch_latency() -> None:
    assert benchmark._nearest_rank_percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0
    assert benchmark._nearest_rank_percentile([4.0, 1.0, 3.0, 2.0], 0.5) == 2.0


@pytest.mark.parametrize("percentile", [0.0, -0.1, 1.1])
def test_nearest_rank_percentile_rejects_invalid_probability(percentile: float) -> None:
    with pytest.raises(ValueError, match="percentile"):
        benchmark._nearest_rank_percentile([1.0], percentile)


def test_evaluate_results_accepts_perf03_contract() -> None:
    results = [
        _result(50_000, total_seconds=2.0),
        _result(100_000, total_seconds=4.5),
        _result(1_000_000, total_seconds=40.0, last_first_ratio=1.5),
    ]

    assert benchmark.evaluate_results(results) == ()


def test_evaluate_results_rejects_superlinear_double_size_pair() -> None:
    results = [
        _result(50_000, total_seconds=2.0),
        _result(100_000, total_seconds=5.1),
    ]

    violations = benchmark.evaluate_results(results)

    assert any("T(100,000)/T(50,000)" in violation for violation in violations)


def test_evaluate_results_rejects_batch_p95_and_session_slowdown() -> None:
    result = _result(
        1_000_000,
        total_seconds=40.0,
        p95_batch_ms=benchmark.MAX_P95_BATCH_MS + 0.1,
        last_first_ratio=benchmark.MAX_LAST_FIRST_WINDOW_RATIO + 0.01,
    )

    violations = benchmark.evaluate_results([result])

    assert any("p95 batch64" in violation for violation in violations)
    assert any("last/first 10k" in violation for violation in violations)


def test_evaluate_results_rejects_noncanonical_batch_size() -> None:
    result = replace(_result(50_000, total_seconds=2.0), batch_size=32)

    violations = benchmark.evaluate_results([result])

    assert any("batch size 32" in violation for violation in violations)


def test_size_parser_rejects_empty_and_duplicate_sizes() -> None:
    with pytest.raises(Exception, match="at least one"):
        benchmark._parse_sizes(",")
    with pytest.raises(Exception, match="unique"):
        benchmark._parse_sizes("50000,50000")
