from __future__ import annotations

from types import SimpleNamespace

import pytest

from geoworkbench.services import process_metrics
from geoworkbench.services.process_metrics import process_memory_snapshot


def test_process_memory_snapshot_is_best_effort_and_non_negative() -> None:
    snapshot = process_memory_snapshot()

    if snapshot.rss_bytes is not None:
        assert snapshot.rss_bytes >= 0
    if snapshot.peak_rss_bytes is not None:
        assert snapshot.peak_rss_bytes >= 0
    if snapshot.rss_bytes is not None and snapshot.peak_rss_bytes is not None:
        assert snapshot.peak_rss_bytes >= snapshot.rss_bytes


@pytest.mark.parametrize("peak_kib,current", [(1, 4096), (8, 4096), (8, None)])
def test_posix_memory_peak_includes_current_observation(
    monkeypatch, peak_kib: int, current: int | None,
) -> None:
    monkeypatch.setattr(process_metrics.sys, "platform", "linux")
    monkeypatch.setitem(
        process_metrics.sys.modules,
        "resource",
        SimpleNamespace(
            RUSAGE_SELF=0,
            getrusage=lambda _who: SimpleNamespace(ru_maxrss=peak_kib),
        ),
    )
    monkeypatch.setattr(process_metrics, "_linux_current_rss_bytes", lambda: current)

    snapshot = process_memory_snapshot()

    assert snapshot.rss_bytes == current
    assert snapshot.peak_rss_bytes == max(peak_kib * 1024, current or 0)
