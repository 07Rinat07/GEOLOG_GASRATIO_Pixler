from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CollapsibleSection(QFrame):
    """Compact section used to keep secondary actions out of the main workflow.

    The header behaves like a normal checkable button, is keyboard accessible and
    preserves the child widget rather than recreating it on every toggle.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        content: QWidget,
        parent: QWidget | None = None,
        *,
        expanded: bool = False,
        tooltip: str = "",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("collapsible-section")
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.header = QToolButton(self)
        self.header.setObjectName("collapsible-section-header")
        self.header.setText(title)
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setAutoRaise(False)
        self.header.setToolTip(tooltip)
        self.header.setStatusTip(tooltip)
        self.header.setAccessibleName(title)

        self.content = content
        self.content.setVisible(expanded)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.header)
        layout.addWidget(self.content)

        self.header.toggled.connect(self.set_expanded)
        self.setStyleSheet(
            "QFrame#collapsible-section { border: 0; }"
            "QToolButton#collapsible-section-header {"
            "  text-align: left; padding: 7px 9px; border: 1px solid #cbd5e1;"
            "  border-radius: 6px; background: #f8fafc; color:#0f172a; font-weight: 600;"
            "}"
            "QToolButton#collapsible-section-header:hover { background: #eef2ff; color:#0f172a; }"
            "QToolButton#collapsible-section-header:disabled { background:#e5e7eb; color:#64748b; }"
        )

    def is_expanded(self) -> bool:
        return self.header.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        expanded = bool(expanded)
        if self.header.isChecked() != expanded:
            self.header.blockSignals(True)
            self.header.setChecked(expanded)
            self.header.blockSignals(False)
        self.header.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.content.setVisible(expanded)
        self.toggled.emit(expanded)
