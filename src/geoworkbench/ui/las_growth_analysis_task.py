"""Keep the GUI responsive while a modal LAS preview owns the controller."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

from geoworkbench.services.application_logging import log_event

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout, QWidget

Result = TypeVar("Result")


class _AnalysisProgress(QDialog):
    def reject(self) -> None:
        # No cancellation of a controller operation midway through its preview.
        # Keep its owning dialog and dataset selection alive until it completes.
        return


def run_las_growth_analysis(
    parent: QWidget, message: str, operation: Callable[[], Result],
) -> Result:
    """Run model-only preview work; all widgets and error handling stay on GUI thread."""
    dialog = _AnalysisProgress(parent)
    dialog.setWindowTitle(parent.windowTitle())
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(message))
    progress = QProgressBar(dialog)
    progress.setRange(0, 0)
    layout.addWidget(progress)
    started = perf_counter()
    log_event("daily_las_growth.analysis.started")
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="las-growth-analysis") as executor:
        future = executor.submit(operation)
        timer = QTimer(dialog)
        timer.setInterval(25)

        def finish_when_ready() -> None:
            if future.done():
                dialog.accept()

        timer.timeout.connect(finish_when_ready)
        timer.start()
        dialog.exec()
        timer.stop()
        try:
            return future.result()
        finally:
            log_event(
                "daily_las_growth.analysis.finished",
                duration_ms=round((perf_counter() - started) * 1000.0, 3),
                failed=future.exception() is not None,
            )
            dialog.deleteLater()
