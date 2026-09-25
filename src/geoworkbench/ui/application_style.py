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
QPushButton[uiRole="primary"]:disabled {
    color: palette(mid);
    background: palette(window);
    border-color: palette(mid);
}

QPushButton#print-center-primary-action {
    padding: 7px 18px;
    font-weight: 700;
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

QFrame#mainToolbar {
    border-bottom: 1px solid palette(mid);
    background: palette(window);
}
QFrame#mainToolbar QToolButton {
    min-height: 32px;
    padding: 4px 9px;
    border: 1px solid palette(mid);
    border-radius: 7px;
    color: palette(button-text);
    font-weight: 600;
    background: palette(button);
}
QFrame#mainToolbar QToolButton:hover {
    background: palette(midlight);
    border-color: palette(highlight);
}
QFrame#mainToolbar QToolButton:pressed,
QFrame#mainToolbar QToolButton:checked {
    background: palette(highlight);
    border-color: palette(highlight);
    color: palette(highlighted-text);
}

QFrame#formEditToolbar {
    background: palette(window);
    border-bottom: 1px solid palette(mid);
}
QFrame#formEditToolbar QToolButton {
    min-height: 28px;
    padding: 3px 7px;
    border-radius: 5px;
}
QFrame#formEditToolbar QToolButton:hover {
    background: palette(midlight);
}
QLabel#formEditToolbarCaption {
    background: transparent;
    font-weight: 700;
    color: palette(window-text);
    padding-right: 8px;
}

QFrame#tabletCurvePencilBar {
    background: palette(window);
    border-top: 1px solid palette(mid);
    border-bottom: 1px solid palette(mid);
}
QFrame#tabletCurvePencilBar[pencilActive="true"] {
    background: palette(alternate-base);
    border-top: 2px solid palette(highlight);
    border-bottom: 2px solid palette(highlight);
}
QFrame#tabletCurvePencilBar QPushButton:checked {
    background: palette(highlight);
    color: palette(highlighted-text);
    border-color: palette(highlight);
    font-weight: 700;
}
QLabel[statusRole="muted"] {
    background: transparent;
    color: palette(window-text);
    padding: 2px 6px;
}
QLabel[statusRole="active"] {
    background: transparent;
    color: palette(window-text);
    border-left: 4px solid palette(highlight);
    padding: 2px 6px;
    font-weight: 700;
}
QLabel[statusRole="error"] {
    color: palette(window-text);
    background: palette(alternate-base);
    border: 2px solid palette(mid);
    border-left: 4px solid palette(highlight);
    padding: 2px 6px;
    font-weight: 700;
}

QLabel#print-center-source,
QLabel#print-center-column-header-title,
QLabel#print-center-action-summary {
    font-weight: 600;
}
QLabel#print-center-header-preview {
    background: palette(base);
    border: 1px solid palette(mid);
}
QLabel#print-center-depth-standard {
    color: palette(mid);
}

QLabel#print-job-status-title {
    font-size: 14px;
    font-weight: 700;
    color: palette(window-text);
}
QLabel#print-job-status-title[statusRole="success"] {
    border-left: 4px solid palette(highlight);
    padding-left: 7px;
}
QLabel#print-job-status-title[statusRole="error"] {
    border: 2px solid palette(mid);
    background: palette(alternate-base);
    padding: 3px 6px;
}

QLabel[validationRole="error"] {
    color: palette(window-text);
    background: palette(alternate-base);
    border-left: 4px solid palette(highlight);
    padding: 3px 7px;
    font-weight: 600;
}
QLabel[validationRole="warning"] {
    color: palette(window-text);
    background: palette(alternate-base);
    border-left: 4px solid palette(mid);
    padding: 3px 7px;
    font-weight: 600;
}
QLabel[validationRole="success"] {
    color: palette(window-text);
    background: palette(base);
    border-left: 4px solid palette(highlight);
    padding: 3px 7px;
}

QLabel[guidanceRole="info"] {
    color: palette(window-text);
    font-size: 11px;
}
QLabel[guidanceRole="warning"] {
    color: palette(window-text);
    background: palette(alternate-base);
    border: 1px solid palette(mid);
    border-left: 4px solid palette(highlight);
    border-radius: 4px;
    padding: 4px 6px;
    font-weight: 600;
}

QLabel#depth-annotations-editor-hint {
    color: palette(window-text);
    background: palette(alternate-base);
    border: 1px solid palette(mid);
    border-left: 4px solid palette(highlight);
    border-radius: 6px;
    padding: 7px 10px;
}
QLabel#depth-annotations-layer-title {
    color: palette(window-text);
    font-weight: 700;
    font-size: 14px;
}
QLabel#depth-annotations-axis-display {
    color: palette(window-text);
    font-weight: 600;
}
QLabel#depth-annotations-drag-hint {
    color: palette(window-text);
    padding-top: 8px;
}

QLabel#las-editor-title {
    color: palette(window-text);
    font-size: 20px;
    font-weight: 700;
}
QLabel#las-editor-summary {
    color: palette(text);
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 10px;
}
QLabel#las-editor-safety-note {
    color: palette(window-text);
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

QDialog#form-create-dialog QTreeWidget::item {
    min-height: 25px;
    padding: 2px 4px;
}

QDialog#form-manager-dialog QTreeWidget::item {
    min-height: 26px;
    padding: 2px 4px;
}
QDialog#form-manager-dialog QTreeWidget::item:hover {
    background: palette(midlight);
}
QLabel#form-manager-heading {
    font-size: 13px;
    color: palette(window-text);
    padding: 2px 4px;
}
QLabel[hintRole="neutral"],
QLabel[hintRole="success"],
QLabel[hintRole="warning"],
QLabel[hintRole="error"] {
    color: palette(window-text);
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 5px;
    padding: 6px 8px;
}
QLabel[hintRole="success"] {
    border-left: 4px solid palette(highlight);
}
QLabel[hintRole="warning"] {
    background: palette(alternate-base);
    border-left: 4px solid palette(mid);
    font-weight: 600;
}
QLabel[hintRole="error"] {
    background: palette(alternate-base);
    border: 2px solid palette(mid);
    border-left: 4px solid palette(highlight);
    font-weight: 600;
}
QLabel[hintRole="neutral"] {
    color: palette(window-text);
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
