from __future__ import annotations

import argparse

import pytest

from benchmarks import benchmark_curve_sampling as benchmark


def _valid_result() -> dict[str, object]:
    return {
        "input_rows": 1_000_000,
        "max_points": 4096,
        "cold_ms": 10.0,
        "hit_ms": 0.01,
        "zoom_ms": 2.0,
        "cold_output_rows": 4096,
        "zoom_output_rows": 4096,
        "cache_entries": 2,
        "cache_current_bytes": 131_072,
        "cache_max_bytes": benchmark.DEFAULT_CACHE_BYTES,
        "cache_hits": 1,
        "cache_misses": 2,
        "cache_evictions": 0,
        "peak_rss_mib": 256.0,
    }


def test_evaluate_result_accepts_structural_perf04_contract() -> None:
    benchmark.evaluate_result(_valid_result())


def test_evaluate_result_rejects_byte_budget_overflow() -> None:
    result = _valid_result()
    result["cache_current_bytes"] = benchmark.DEFAULT_CACHE_BYTES + 1

    with pytest.raises(AssertionError, match="byte budget"):
        benchmark.evaluate_result(result)


def test_evaluate_result_rejects_changed_cache_request_contract() -> None:
    result = _valid_result()
    result["cache_hits"] = 0

    with pytest.raises(AssertionError, match="cold/hit/zoom"):
        benchmark.evaluate_result(result)


def test_curve_benchmark_worker_exercises_cold_hit_and_zoom() -> None:
    result = benchmark.run_benchmark_worker(10_000, max_points=128, cache_bytes=1_048_576)

    assert result["input_rows"] == 10_000
    assert result["cache_hits"] == 1
    assert result["cache_misses"] == 2
    assert result["cache_entries"] == 2
    assert 0 < result["cache_current_bytes"] <= result["cache_max_bytes"]
    assert result["peak_rss_mib"] > 0


def test_size_parser_rejects_empty_duplicate_and_non_positive_sizes() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="at least one"):
        benchmark._parse_sizes(",")
    with pytest.raises(argparse.ArgumentTypeError, match="unique"):
        benchmark._parse_sizes("1000000,1000000")
    with pytest.raises(argparse.ArgumentTypeError, match="positive"):
        benchmark._parse_sizes("0,1000000")


def test_positive_int_rejects_zero() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="positive"):
        benchmark._positive_int("0")
