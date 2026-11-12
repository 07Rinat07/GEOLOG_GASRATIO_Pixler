"""Background execution of a snapshot-bound read-only GIS interval review."""

from __future__ import annotations

import logging
from threading import Event
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from geoworkbench.domain.models import Dataset
from geoworkbench.services.gis_interval_sample_review import (
    GisIntervalReviewCancelled, review_gis_source_interval_batch,
)
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot, GisIntervalSourceChanged


_LOG = logging.getLogger(__name__)


class GisIntervalCompareWorker(QThread):
    progress = Signal(str, int, int)
    completed = Signal(object, object)
    failed = Signal(str)

    def __init__(self, dataset: Dataset, keys: tuple[str, ...], top: float, bottom: float) -> None:
        super().__init__()
        self.dataset = dataset
        self.keys = keys
        self.top = top
        self.bottom = bottom
        self._cancel = Event()

    def cancellation_callback(self) -> Callable[..., None]:
        """Return a plain Python callback that never retains the Qt wrapper."""
        event = self._cancel

        def cancel(*_args: object) -> None:
            event.set()

        return cancel

    def request_cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            self.progress.emit("preparing", 0, 0)
            snapshot = GisIntervalSnapshot(self.dataset, self.keys, self._cancel.is_set)
            self.progress.emit("checking", 0, 0)
            results = review_gis_source_interval_batch(
                snapshot.dataset, curve_keys=self.keys, top_md_m=self.top, bottom_md_m=self.bottom,
                cancelled=self._cancel.is_set,
                progress=lambda done, total: self.progress.emit("reviewing", done, total),
            )
            self.progress.emit("verifying", 0, 0)
            if not snapshot.matches(self._cancel.is_set):
                raise GisIntervalSourceChanged("GIS source changed during review")
            if self._cancel.is_set():
                raise GisIntervalReviewCancelled
            self.completed.emit(snapshot, results)
        except GisIntervalReviewCancelled:
            self.failed.emit("cancelled")
        except GisIntervalSourceChanged:
            self.failed.emit("changed")
        except Exception:
            # Worker errors are reported generically; source paths are not shown in the UI.
            _LOG.exception("Background GIS interval review failed")
            self.failed.emit("failed")
