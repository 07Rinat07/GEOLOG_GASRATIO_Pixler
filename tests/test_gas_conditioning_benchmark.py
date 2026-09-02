from __future__ import annotations

import numpy as np
import pytest

from benchmarks.benchmark_gas_conditioning import (
    BenchmarkBudget,
    BenchmarkResult,
    evaluate_results,
    make_deterministic_fixture,
    validate_repeats,
)


def _result(
    rows: int,
    *,
    median_seconds: float,
    peak_rss_mib: float,
) -> BenchmarkResult:
    return BenchmarkResult(
        rows=rows,
        components=7,
        repeats=3,
        best_seconds=median_seconds * 0.95,
        median_seconds=median_seconds,
        rows_per_second=rows / median_seconds,
        peak_rss_mib=peak_rss_mib,
        interpolated_rows=0,
        derived_curves=20,
        samples_seconds=(median_seconds, median_seconds, median_seconds),
    )


def test_deterministic_fixture_repeats_exactly() -> None:
    first_depth, first_components = make_deterministic_fixture(1_000)
    second_depth, second_components = make_deterministic_fixture(1_000)

    np.testing.assert_array_equal(first_depth, second_depth)
    assert first_components.keys() == second_components.keys()
    for mnemonic in first_components:
        np.testing.assert_array_equal(
            first_components[mnemonic],
            second_components[mnemonic],
        )


def test_deterministic_fixture_rejects_too_few_rows() -> None:
    with pytest.raises(ValueError, match="at least 100 rows"):
        make_deterministic_fixture(99)


def test_benchmark_requires_three_repetitions() -> None:
    with pytest.raises(ValueError, match="at least 3 repetitions"):
        validate_repeats(2)


def test_evaluate_results_accepts_linear_growth_inside_budget() -> None:
    results = [
        _result(100_000, median_seconds=0.20, peak_rss_mib=120.0),
        _result(1_000_000, median_seconds=1.90, peak_rss_mib=600.0),
    ]
    budgets = {
        100_000: BenchmarkBudget(max_median_seconds=1.0, max_peak_rss_mib=256.0),
        1_000_000: BenchmarkBudget(max_median_seconds=5.0, max_peak_rss_mib=1024.0),
    }

    assert evaluate_results(results, budgets=budgets) == ()


def test_evaluate_results_reports_absolute_budget_regression() -> None:
    result = _result(100_000, median_seconds=2.0, peak_rss_mib=300.0)
    budgets = {
        100_000: BenchmarkBudget(max_median_seconds=1.0, max_peak_rss_mib=256.0),
    }

    violations = evaluate_results([result], budgets=budgets)

    assert any("median time" in violation for violation in violations)
    assert any("peak RSS" in violation for violation in violations)


def test_evaluate_results_reports_clearly_superlinear_growth() -> None:
    results = [
        _result(100_000, median_seconds=0.10, peak_rss_mib=100.0),
        _result(1_000_000, median_seconds=2.10, peak_rss_mib=1_600.0),
    ]

    violations = evaluate_results(results, budgets={})

    assert any("time scaling" in violation for violation in violations)
    assert any("RSS scaling" in violation for violation in violations)
