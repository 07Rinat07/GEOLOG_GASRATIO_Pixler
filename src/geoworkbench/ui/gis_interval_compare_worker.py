"""Background execution of a snapshot-bound read-only GIS interval review."""

from __future__ import annotations

import logging
from collections.abc import Callable
from queue import Empty, SimpleQueue
from threading import Event, Thread

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_interval_sample_review import (
    GisIntervalReviewCancelled, GisSourceIntervalBatchItem, review_gis_source_interval_batch,
)
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot, GisIntervalSourceChanged


_LOG = logging.getLogger(__name__)


class _ReviewState:
    """Python-only state; the background thread never needs a QObject."""

    def __init__(self) -> None:
        self.cancel = Event()
        self.progress: SimpleQueue[tuple[str, int, int]] = SimpleQueue()
        self.result: tuple[GisIntervalSnapshot, tuple[GisSourceIntervalBatchItem, ...]] | None = None
        self.failure = "failed"


def _run_review(
    dataset: Dataset, keys: tuple[str, ...], top: float, bottom: float, state: _ReviewState,
) -> None:
    try:
        state.progress.put(("preparing", 0, 0))
        snapshot = GisIntervalSnapshot(dataset, keys, state.cancel.is_set)
        state.progress.put(("checking", 0, 0))
        results = review_gis_source_interval_batch(
            snapshot.dataset, curve_keys=keys, top_md_m=top, bottom_md_m=bottom,
            cancelled=state.cancel.is_set,
            progress=lambda done, total: state.progress.put(("reviewing", done, total)),
        )
        state.progress.put(("verifying", 0, 0))
        if not snapshot.matches(state.cancel.is_set):
            raise GisIntervalSourceChanged("GIS source changed during review")
        if state.cancel.is_set():
            raise GisIntervalReviewCancelled
        state.result = (snapshot, results)
    except GisIntervalReviewCancelled:
        state.failure = "cancelled"
    except GisIntervalSourceChanged:
        state.failure = "changed"
    except Exception:
        # Worker errors are reported generically; source paths are not shown in the UI.
        _LOG.exception("Background GIS interval review failed")


class GisIntervalCompareWorker(QObject):
    """GUI-owned signal bridge; the numeric thread uses only Python state."""
    progress = Signal(str, int, int)
    completed = Signal(object, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, dataset: Dataset, keys: tuple[str, ...], top: float, bottom: float) -> None:
        super().__init__()
        self.dataset = dataset
        self.keys = keys
        self.top = top
        self.bottom = bottom
        self._state = _ReviewState()
        self._cancel = self._state.cancel
        self._started = False
        self._poll = QTimer(self)
        self._poll.setInterval(10)
        self._poll.timeout.connect(self._deliver)
        self._thread = Thread(
            target=_run_review, args=(dataset, keys, top, bottom, self._state),
            name="gis-interval-review", daemon=False,
        )

    def start(self) -> None:
        if self._started:
            raise RuntimeError("A GIS review worker can only start once")
        self._started = True
        try:
            self._thread.start()
        except RuntimeError:
            _LOG.exception("Could not start background GIS interval review")
        self._poll.start()

    def wait(self) -> bool:
        # Thread.join is invalid before a successful start. Only the GUI
        # owner or application shutdown joins this pure Python thread.
        if self._thread.ident is not None:
            self._thread.join()
        return not self._thread.is_alive()

    def isFinished(self) -> bool:  # noqa: N802 - existing worker interface
        return self._started and not self._thread.is_alive()

    def cancellation_callback(self) -> Callable[..., None]:
        """Return a plain Python callback that never retains the Qt wrapper."""
        event = self._cancel

        def cancel(*_args: object) -> None:
            event.set()

        return cancel

    def request_cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def _deliver(self) -> None:
        # All Qt operations, including signal emission and retirement, happen
        # on the owning GUI thread. Join before reading a terminal result.
        finished = not self._thread.is_alive()
        if finished:
            self._poll.stop()
            self.wait()
        while True:
            try:
                stage, current, total = self._state.progress.get_nowait()
            except Empty:
                break
            self.progress.emit(stage, current, total)
        if not finished:
            return
        result = self._state.result
        self._state.result = None
        if result is not None:
            self.completed.emit(*result)
        else:
            self.failed.emit(self._state.failure)
        self.finished.emit()
