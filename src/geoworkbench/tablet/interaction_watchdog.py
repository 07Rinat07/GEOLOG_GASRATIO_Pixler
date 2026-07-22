from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication

from geoworkbench.tablet.interaction_router import TabletInteractionRouter


class TabletInteractionWatchdog(QObject):
    """Recover an edit gesture when the native release event is lost.

    Windows may drop a mouse-release event when a modal dialog, Alt+Tab or a
    monitor boundary changes the active native window.  The router itself never
    owns a native grab, so this lightweight guard only checks the actual button
    state and asks the adapter to synthesize one final release when required.
    """

    def __init__(
        self,
        router: TabletInteractionRouter,
        recover_release: Callable[[], None],
        parent: QObject | None = None,
        *,
        interval_ms: int = 80,
    ) -> None:
        super().__init__(parent)
        self._router = router
        self._recover_release = recover_release
        self._timer = QTimer(self)
        self._timer.setInterval(max(30, int(interval_ms)))
        self._timer.timeout.connect(self._poll)

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    def sync(self) -> None:
        if self._router.has_active_capture:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()

    def stop(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        if not self._router.has_active_capture:
            self._timer.stop()
            return
        if QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            return
        self._recover_release()
        self.sync()
