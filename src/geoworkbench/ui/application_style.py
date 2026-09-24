from __future__ import annotations

from PySide6.QtWidgets import QApplication


_ADAPTIVE_STYLE_PROPERTY = "_geologAdaptiveUiInstalled"


def adaptive_application_stylesheet() -> str:
    """Return the shared palette-aware UI contract for desktop controls.

    The stylesheet deliberately avoids fixed widget widths and hard-coded light/dark
    colours. Qt palette roles keep it compatible with Windows light/dark themes,
    while logical-pixel minimum heights remain DPI-aware.
    """

    return """
/* Geolog adaptive UI foundation */
QPushButton {
    min-height: 28px;
    padding: 4px 10px;
    border: 1px solid palette(mid);
    border-radius: 5px;
    background: palette(button);
    color: palette(button-text);
}
QPushButton:hover {
    background: palette(midlight);
}
QPushButton:pressed, QPushButton:checked {
    background: palette(highlight);
    color: palette(highlighted-text);
}
QPushButton:focus {
    border: 2px solid palette(highlight);
    padding: 3px 9px;
}
QPushButton:disabled {
    color: palette(mid);
    background: palette(window);
}

QPushButton[uiRole="primary"] {
    background: palette(highlight);
    color: palette(highlighted-text);
    font-weight: 600;
}
QPushButton[uiRole="secondary"] {
    background: palette(button);
    color: palette(button-text);
}
QPushButton[uiRole="quiet"] {
    background: transparent;
    border-color: transparent;
}
QPushButton[uiRole="destructive"] {
    font-weight: 600;
    border-width: 2px;
}

QToolButton {
    min-height: 28px;
    min-width: 28px;
    padding: 3px 6px;
    border: 1px solid transparent;
    border-radius: 5px;
}
QToolButton:hover {
    background: palette(midlight);
    border-color: palette(mid);
}
QToolButton:pressed, QToolButton:checked {
    background: palette(highlight);
    color: palette(highlighted-text);
}
QToolButton:focus {
    border: 2px solid palette(highlight);
}

QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QDateEdit,
QDateTimeEdit,
QTimeEdit {
    min-height: 28px;
    padding: 3px 7px;
    border: 1px solid palette(mid);
    border-radius: 4px;
    background: palette(base);
    color: palette(text);
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
}
QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QDateEdit:focus,
QDateTimeEdit:focus,
QTimeEdit:focus {
    border: 2px solid palette(highlight);
    padding: 2px 6px;
}
QLineEdit:disabled,
QComboBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled {
    color: palette(mid);
    background: palette(window);
}
QLineEdit:read-only,
QTextEdit:read-only,
QPlainTextEdit:read-only {
    color: palette(text);
    background: palette(window);
}

QTextEdit,
QPlainTextEdit,
QListView,
QTreeView,
QTableView,
QListWidget,
QTreeWidget,
QTableWidget {
    border: 1px solid palette(mid);
    border-radius: 4px;
    background: palette(base);
    color: palette(text);
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
}

QTabWidget::pane {
    border: 1px solid palette(mid);
    border-radius: 4px;
}
QTabBar::tab {
    min-height: 26px;
    padding: 5px 10px;
    margin-right: 1px;
}
QTabBar::tab:selected {
    font-weight: 600;
}

QGroupBox {
    margin-top: 10px;
    padding-top: 7px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    font-weight: 600;
}

QMenu::item {
    min-height: 24px;
    padding: 4px 24px 4px 8px;
}
QMenu::item:selected {
    background: palette(highlight);
    color: palette(highlighted-text);
}

QToolTip {
    color: palette(text);
    background-color: palette(base);
    border: 1px solid palette(mid);
    padding: 4px 6px;
    opacity: 255;
}
"""


def apply_adaptive_application_style(app: QApplication) -> None:
    """Install the shared style once without replacing application palette."""

    if bool(app.property(_ADAPTIVE_STYLE_PROPERTY)):
        return
    current = app.styleSheet().rstrip()
    shared = adaptive_application_stylesheet().strip()
    app.setStyleSheet(f"{current}\n{shared}" if current else shared)
    app.setProperty(_ADAPTIVE_STYLE_PROPERTY, True)


__all__ = [
    "adaptive_application_stylesheet",
    "apply_adaptive_application_style",
]
