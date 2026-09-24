from __future__ import annotations

import pytest

from benchmarks.benchmark_wits_preview import PreviewMemoryResult, evaluate_results


def _result(frames: int, *, peak: float, rows: int, records: int) -> PreviewMemoryResult:
    return PreviewMemoryResult(
        frames=frames, buffer_frames=100, baseline_rss_mib=90.0, peak_rss_mib=peak,
        elapsed_seconds=1.0, retained_frames=100, retained_rows=rows,
        retained_records=records, compactions=int(frames > 100),
        evicted_frames=frames - 100,
    )


def test_gate_accepts_bounded_tenfold_preview_stream() -> None:
    assert evaluate_results(
        _result(100, peak=130.0, rows=100, records=100),
        _result(1000, peak=155.0, rows=200, records=200),
    ) == ()


def test_gate_rejects_hidden_session_growth_even_when_dataset_is_bounded() -> None:
    violations = evaluate_results(
        _result(100, peak=130.0, rows=100, records=100),
        _result(1000, peak=155.0, rows=200, records=1000),
    )
    assert any("session records" in violation for violation in violations)


def test_gate_rejects_rss_growth_without_oversized_retained_arrays() -> None:
    violations = evaluate_results(
        _result(100, peak=130.0, rows=100, records=100),
        _result(1000, peak=240.0, rows=200, records=200),
    )
    assert any("peak RSS growth" in violation for violation in violations)


def test_gate_refuses_incomparable_fixtures() -> None:
    with pytest.raises(ValueError, match="at least 10x"):
        evaluate_results(
            _result(100, peak=130.0, rows=100, records=100),
            _result(200, peak=150.0, rows=200, records=200),
        )
