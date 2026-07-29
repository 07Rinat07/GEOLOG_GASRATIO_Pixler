from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QSizePolicy, QStyle, QToolBar, QWidget


class AdaptiveActionToolBar(QToolBar):
    """Compact editor toolbar with native Qt overflow handling.

    QToolBar automatically moves actions that no longer fit into its extension
    menu. This keeps dialogs usable on smaller screens without clipping button
    captions or forcing a fixed minimum width.
    """

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QSize(18, 18))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setContentsMargins(0, 0, 0, 0)

    def add_standard_action(
        self,
        text: str,
        callback: Callable[[], None],
        *,
        icon: QStyle.StandardPixmap | None = None,
        tooltip: str | None = None,
        checkable: bool = False,
    ) -> QAction:
        action = QAction(
            self.style().standardIcon(icon) if icon is not None else text,
            text if icon is not None else self,
        )
        if icon is None:
            action = QAction(text, self)
        action.setToolTip(tooltip or text)
        action.setStatusTip(tooltip or text)
        action.setCheckable(checkable)
        action.triggered.connect(lambda _checked=False: callback())
        self.addAction(action)
        return action

    def add_stretch(self) -> QWidget:
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)
        return spacer
