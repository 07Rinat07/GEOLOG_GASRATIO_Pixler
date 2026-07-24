from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.ui.interval_overlay_geometry import (
    OverlayGeometry,
    constrain_overlay_geometry,
    right_anchored_overlay_geometry,
)


class IntervalStatisticsOverlay(QFrame):
    """Movable child overlay that never changes the main-window layout.

    Unlike a floating ``QDockWidget``, this widget remains a child of the tab
    workspace.  It can cover the right edge of the tablet, but cannot leave the
    application viewport or force the top-level window beyond the monitor.
    """

    visibilityChanged = Signal(bool)
    movedByUser = Signal()
    closeRequested = Signal()

    def __init__(
        self,
        title: str,
        content: QWidget,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("intervalStatisticsOverlay")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QFrame#intervalStatisticsOverlay {"
            "background: palette(window); border: 1px solid palette(mid);"
            "border-radius: 5px;}"
            "QWidget#intervalStatisticsOverlayTitle {"
            "background: palette(alternate-base); border-bottom: 1px solid palette(mid);}"
            "QLabel#intervalStatisticsOverlayTitleLabel {font-weight: 600; padding-left: 4px;}"
            "QToolButton#intervalStatisticsOverlayClose {border: 0; padding: 2px;}"
            "QToolButton#intervalStatisticsOverlayClose:hover {background: palette(midlight);}"
        )
        self._content = content
        self._content.setParent(self)
        self._drag_origin_global: QPoint | None = None
        self._drag_origin_local: QPoint | None = None
        self._user_positioned = False
        self._toggle_action = QAction(title, self)
        self._toggle_action.setCheckable(True)
        self._toggle_action.toggled.connect(self._toggle_requested)

        self._title_bar = QWidget(self)
        self._title_bar.setObjectName("intervalStatisticsOverlayTitle")
        self._title_bar.setCursor(Qt.CursorShape.SizeAllCursor)
        self._title_label = QLabel(title, self._title_bar)
        self._title_label.setObjectName("intervalStatisticsOverlayTitleLabel")
        self._close_button = QToolButton(self._title_bar)
        self._close_button.setObjectName("intervalStatisticsOverlayClose")
        self._close_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton)
        )
        self._close_button.setAutoRaise(True)
        self._close_button.clicked.connect(self._request_close)

        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(5, 3, 3, 3)
        title_layout.setSpacing(4)
        title_layout.addWidget(self._title_label, 1)
        title_layout.addWidget(self._close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._title_bar)
        layout.addWidget(self._content, 1)

        self._title_bar.installEventFilter(self)
        self._title_label.installEventFilter(self)
        parent.installEventFilter(self)
        self.hide()

    def toggleViewAction(self) -> QAction:  # noqa: N802 - QDockWidget compatibility
        return self._toggle_action

    def isFloating(self) -> bool:  # noqa: N802 - QDockWidget compatibility
        return True

    def setWindowTitle(self, title: str) -> None:  # noqa: N802 - Qt API
        super().setWindowTitle(title)
        self._title_label.setText(title)
        self._toggle_action.setText(title)

    @property
    def user_positioned(self) -> bool:
        return self._user_positioned

    def reset_user_position(self) -> None:
        self._user_positioned = False

    def show_preserving_position(self) -> None:
        self.constrain_to_parent(anchor_right=not self._user_positioned)
        self.show()
        self.raise_()

    def constrain_to_parent(self, *, anchor_right: bool = False) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        parent_size = parent.size()
        preferred_width = min(390, max(300, parent_size.width() // 4))
        preferred_height = min(720, max(320, parent_size.height() - 24))
        if anchor_right or not self._user_positioned:
            geometry = right_anchored_overlay_geometry(
                parent_width=parent_size.width(),
                parent_height=parent_size.height(),
                preferred_width=preferred_width,
                preferred_height=preferred_height,
                margin=8,
                top_offset=8,
            )
        else:
            geometry = constrain_overlay_geometry(
                parent_width=parent_size.width(),
                parent_height=parent_size.height(),
                requested_x=self.x(),
                requested_y=self.y(),
                requested_width=self.width(),
                requested_height=self.height(),
                margin=8,
            )
        self._apply_geometry(geometry)

    def move_constrained(self, requested_position: QPoint, *, user_move: bool = True) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        geometry = constrain_overlay_geometry(
            parent_width=parent.width(),
            parent_height=parent.height(),
            requested_x=requested_position.x(),
            requested_y=requested_position.y(),
            requested_width=self.width(),
            requested_height=self.height(),
            margin=8,
        )
        self._apply_geometry(geometry)
        if user_move:
            self._user_positioned = True
            self.movedByUser.emit()

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # noqa: N802
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            if self.isVisible():
                QTimer.singleShot(0, self._constrain_after_parent_resize)
            return False
        if watched is self._title_bar or watched is self._title_label:
            if event.type() == QEvent.Type.MouseButtonPress:
                mouse_event = event
                if (
                    isinstance(mouse_event, QMouseEvent)
                    and mouse_event.button() == Qt.MouseButton.LeftButton
                ):
                    self._drag_origin_global = mouse_event.globalPosition().toPoint()
                    self._drag_origin_local = self.pos()
                    self.raise_()
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                mouse_event = event
                if (
                    isinstance(mouse_event, QMouseEvent)
                    and self._drag_origin_global is not None
                    and self._drag_origin_local is not None
                    and mouse_event.buttons() & Qt.MouseButton.LeftButton
                ):
                    delta = mouse_event.globalPosition().toPoint() - self._drag_origin_global
                    self.move_constrained(self._drag_origin_local + delta, user_move=True)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_origin_global = None
                self._drag_origin_local = None
                return True
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.constrain_to_parent(anchor_right=not self._user_positioned)
        super().showEvent(event)
        self._sync_action(True)
        self.visibilityChanged.emit(True)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().hideEvent(event)
        self._sync_action(False)
        self.visibilityChanged.emit(False)

    def _constrain_after_parent_resize(self) -> None:
        if self.isVisible():
            self.constrain_to_parent(anchor_right=False)
            self.raise_()

    def _toggle_requested(self, visible: bool) -> None:
        if visible:
            self.show_preserving_position()
        else:
            self.closeRequested.emit()

    def _request_close(self) -> None:
        self.closeRequested.emit()

    def _sync_action(self, visible: bool) -> None:
        blocked = self._toggle_action.blockSignals(True)
        try:
            self._toggle_action.setChecked(visible)
        finally:
            self._toggle_action.blockSignals(blocked)

    def _apply_geometry(self, geometry: OverlayGeometry) -> None:
        self.setGeometry(geometry.x, geometry.y, geometry.width, geometry.height)
