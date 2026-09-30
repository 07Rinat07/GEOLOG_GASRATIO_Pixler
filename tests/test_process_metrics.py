from __future__ import annotations

from geoworkbench.services.process_metrics import process_memory_snapshot


def test_process_memory_snapshot_is_best_effort_and_non_negative() -> None:
    snapshot = process_memory_snapshot()

    if snapshot.rss_bytes is not None:
        assert snapshot.rss_bytes >= 0
    if snapshot.peak_rss_bytes is not None:
        assert snapshot.peak_rss_bytes >= 0
    if snapshot.rss_bytes is not None and snapshot.peak_rss_bytes is not None:
        assert snapshot.peak_rss_bytes >= snapshot.rss_bytes
