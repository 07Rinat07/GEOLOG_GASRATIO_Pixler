from threading import Event, Timer

import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt

from geoworkbench.services.gis_interval_sample_review import review_gis_source_interval_batch
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot
from geoworkbench.ui import gis_interval_compare_worker as worker_module
from geoworkbench.ui.gis_interval_compare_dialog import (
    GisIntervalCompareDialog, _LIVE_WORKERS, _stop_workers_on_exit,
)
from test_gis_interval_compare import _two_curves
from test_gis_interval_compare_ui import _wait_review


def _paused_review(monkeypatch):
    started, release = Event(), Event()
    original = worker_module.review_gis_source_interval_batch

    def wait_then_review(*args, **kwargs):
        started.set()
        if not release.wait(5):
            raise RuntimeError("Test worker was not released")
        return original(*args, **kwargs)

    monkeypatch.setattr(worker_module, "review_gis_source_interval_batch", wait_then_review)
    return started, release


def test_review_keeps_event_loop_responsive_and_cancel_discards_results(qapp, monkeypatch):
    started, release = _paused_review(monkeypatch)
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        assert started.wait(5) and dialog._worker is not None
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qapp.processEvents()
        assert heartbeat == [True] and not dialog.table.isEnabled()
        dialog.cancel.click()
        assert dialog.status.text() == dialog._t("cancelling")
        release.set()
        _wait_review(qapp, dialog)
        assert dialog.status.text() == dialog._t("cancelled")
        assert dialog.table.item(0, 4).text() == "—" and dialog.table.isEnabled()
    finally:
        release.set()
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_inplace_source_change_during_review_discards_snapshot(qapp, monkeypatch):
    started, release = _paused_review(monkeypatch)
    dataset = _two_curves()
    dialog = GisIntervalCompareDialog(dataset, top="100", bottom="102")
    try:
        dialog.table.item(1, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        assert started.wait(5)
        dataset.curves["RT"].values[0] = 99.0
        release.set()
        _wait_review(qapp, dialog)
        assert dialog.status.text() == dialog._t("changed")
        assert dialog.table.item(1, 4).text() == "—"
    finally:
        release.set()
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_worker_failure_is_reported_without_internal_details(qapp, monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("internal-source-details")

    monkeypatch.setattr(worker_module, "review_gis_source_interval_batch", fail)
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.status.text() == dialog._t("failed")
        assert "internal-source-details" not in dialog.status.text()
        assert dialog.table.item(0, 4).text() == "—"
    finally:
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_closing_during_review_cancels_and_waits_without_blocking(qapp, monkeypatch):
    started, release = _paused_review(monkeypatch)
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    dialog.show()
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        assert started.wait(5)
        worker = dialog._worker
        assert worker is not None
        order = []

        def observe_terminal():
            assert dialog.isVisible()
            assert dialog._worker is None and worker not in _LIVE_WORKERS
            order.append("terminal")

        worker.finished.connect(observe_terminal, Qt.ConnectionType.DirectConnection)
        dialog.rejected.connect(lambda: order.append("rejected"))
        dialog.close()
        assert dialog.isVisible() and dialog._worker is not None
        assert dialog.status.text() == dialog._t("cancelling")
        release.set()
        _wait_review(qapp, dialog)
        assert not dialog.isVisible()
        assert order == ["terminal", "rejected"]
    finally:
        release.set()
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_real_worker_reports_curve_progress_and_completes(qapp, monkeypatch):
    started, release = _paused_review(monkeypatch)
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    try:
        for row in range(2):
            dialog.table.item(row, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        assert started.wait(5) and dialog._worker is not None
        progress = []
        dialog._worker.progress.connect(lambda stage, current, total: progress.append((stage, current, total)))
        release.set()
        _wait_review(qapp, dialog)
        assert ("reviewing", 1, 2) in progress and ("reviewing", 2, 2) in progress
        assert any(stage == "verifying" for stage, _, _ in progress)
        assert dialog.status.text() == dialog._t("complete")
    finally:
        release.set()
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_shutdown_cancels_worker_before_application_exit(qapp, monkeypatch):
    started, release = _paused_review(monkeypatch)
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        assert started.wait(5) and dialog._worker is not None
        worker = dialog._worker
        Timer(0.05, release.set).start()
        _stop_workers_on_exit()
        assert worker.isFinished()
        _wait_review(qapp, dialog)
        assert dialog.table.item(0, 4).text() == "—"
    finally:
        release.set()
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_large_synthetic_review_processes_gui_events(qapp):
    dataset = _two_curves()
    count = 1_000_000
    dataset.active_index.values = np.arange(count, dtype=float)
    dataset.depth = dataset.active_index.values
    dataset.curves["GR"].values = np.ones(count)
    dataset.curves["RT"].values = np.full(count, 2.0)
    dataset.curves["RT"].values[100:102] = np.nan
    dialog = GisIntervalCompareDialog(dataset, top="0", bottom=str(count - 1))
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(True))
    try:
        for row in range(2):
            dialog.table.item(row, 0).setCheckState(Qt.CheckState.Checked)
        timer.start(1)
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert ticks and dialog.status.text() == dialog._t("complete")
        assert dialog.table.item(1, 4).text() == "999998 / 1000000"
        assert dialog.table.item(1, 5).text() == "2"
    finally:
        timer.stop()
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_queued_gis_review_rejects_inplace_change_after_worker_verification(qapp):
    """A source edit between worker emit and the GUI slot must invalidate results."""
    for change in ("curve_values", "axis_values"):
        dataset = _two_curves()
        dialog = GisIntervalCompareDialog(dataset, top="100", bottom="102")
        try:
            dialog.table.item(1, 0).setCheckState(Qt.CheckState.Checked)
            snapshot = GisIntervalSnapshot(dataset, ("RT",), lambda: False)
            result = review_gis_source_interval_batch(
                snapshot.dataset, curve_keys=("RT",), top_md_m=100, bottom_md_m=102,
            )
            assert result[0].review is not None
            assert snapshot.matches(lambda: False)

            # Model Qt queued delivery: the worker has already emitted a
            # verified result, but the GUI has not handled the signal yet.
            if change == "curve_values":
                dataset.curves["RT"].values[0] = 99.0
            else:
                dataset.active_index.values[0] = 99.0
            assert snapshot.structure_matches()  # old GUI check was insufficient
            assert not snapshot.matches(lambda: False)

            dialog._completed(snapshot, result)
            assert dialog.status.text() == dialog._t("changed")
            assert dialog.table.item(1, 4).text() == "—"
            assert dialog.table.item(1, 8).text() == "—"
            assert dialog.missing_details.text() == dialog._t("missing_select")
        finally:
            dialog.close()


def test_repeated_reviews_join_worker_and_remove_cancel_connection(qapp):
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        for _ in range(12):
            dialog.review.click()
            worker = dialog._worker
            assert worker is not None and worker in _LIVE_WORKERS
            assert worker.parent() is not None
            assert dialog._worker_cancel_connection is not None
            _wait_review(qapp, dialog)
            assert dialog._worker_cancel_connection is None
            assert worker not in _LIVE_WORKERS
            assert dialog.status.text() == dialog._t("complete")
    finally:
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_destroyed_dialog_cancels_without_retaining_worker_wrapper(qapp, monkeypatch):
    from time import monotonic, sleep

    started, release = _paused_review(monkeypatch)
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    worker = None
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        assert started.wait(5)
        worker = dialog._worker
        assert worker is not None
        cancel_event = worker._cancel
        dialog.deleteLater()
        # Target only this dialog, not every deferred native object in Qt.
        QCoreApplication.sendPostedEvents(dialog, QEvent.Type.DeferredDelete)
        assert cancel_event.is_set()
        assert worker in _LIVE_WORKERS
    finally:
        release.set()
        if worker is not None:
            deadline = monotonic() + 10
            while worker in _LIVE_WORKERS and monotonic() < deadline:
                qapp.processEvents()
                sleep(0.005)
            assert worker not in _LIVE_WORKERS


def test_numeric_review_runs_on_python_thread_and_returns_to_gui(qapp, monkeypatch):
    from threading import get_ident
    from PySide6.QtCore import QThread

    owner = get_ident()
    seen = []
    original = worker_module.review_gis_source_interval_batch

    def record(*args, **kwargs):
        seen.append(get_ident())
        return original(*args, **kwargs)

    monkeypatch.setattr(worker_module, "review_gis_source_interval_batch", record)
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        worker = dialog._worker
        assert worker is not None and not isinstance(worker, QThread)
        _wait_review(qapp, dialog)
        assert len(seen) == 1 and seen[0] != owner
        assert dialog.status.text() == dialog._t("complete")
        assert dialog.table.item(0, 4).text() == "2 / 3"
        assert worker not in _LIVE_WORKERS
    finally:
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_python_thread_start_failure_retires_worker_and_restores_controls(qapp, monkeypatch):
    def fail_start(_thread):
        raise RuntimeError("thread allocation failure")

    monkeypatch.setattr(worker_module.Thread, "start", fail_start)
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        worker = dialog._worker
        assert worker is not None
        _wait_review(qapp, dialog)
        assert worker not in _LIVE_WORKERS
        assert dialog._worker_cancel_connection is None
        assert dialog.review.isEnabled() and dialog.table.isEnabled()
        assert dialog.status.text() == dialog._t("failed")
        assert dialog.table.item(0, 4).text() == "—"
    finally:
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()


def test_worker_signals_are_emitted_only_on_gui_thread(qapp, monkeypatch):
    """Direct connections expose the emitting thread, not queued receiver affinity."""
    from threading import get_ident

    started, release = _paused_review(monkeypatch)
    owner = get_ident()
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    seen = []
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        assert started.wait(5)
        worker = dialog._worker
        assert worker is not None
        direct = Qt.ConnectionType.DirectConnection
        worker.progress.connect(lambda *_: seen.append(("progress", get_ident())), direct)
        worker.completed.connect(lambda *_: seen.append(("completed", get_ident())), direct)
        worker.failed.connect(lambda *_: seen.append(("failed", get_ident())), direct)
        worker.finished.connect(lambda: seen.append(("finished", get_ident())), direct)
        release.set()
        _wait_review(qapp, dialog)
        assert seen
        assert {thread for _, thread in seen} == {owner}
        assert [kind for kind, _ in seen if kind != "progress"] == ["completed", "finished"]
        assert dialog.status.text() == dialog._t("complete")
        assert worker not in _LIVE_WORKERS
    finally:
        release.set()
        if dialog._worker is not None:
            _wait_review(qapp, dialog)
        dialog.close()
