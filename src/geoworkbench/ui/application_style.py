from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


_ADAPTIVE_STYLE_PROPERTY = "_geologAdaptiveUiInstalled"



@dataclass(frozen=True, slots=True)
class IndustrialBlueTheme:
    """Centralized visual tokens for the DIGITAL GEOLOG desktop UI."""

    shell_background: str = "#071A2B"
    shell_surface: str = "#0B2A44"
    shell_surface_hover: str = "#123C5C"
    shell_border: str = "#274B68"
    work_background: str = "#EDF4F8"
    panel_background: str = "#FFFFFF"
    panel_alternate: str = "#E3EDF4"
    border: str = "#B8CAD7"
    text: str = "#122B3E"
    muted_text: str = "#60798B"
    shell_text: str = "#F7FBFE"
    accent: str = "#00A6E2"
    accent_hover: str = "#19B7EE"
    accent_pressed: str = "#0087BA"
    selection: str = "#D8F2FC"
    disabled_text: str = "#5D7587"
    shell_disabled_text: str = "#8EADC2"


INDUSTRIAL_BLUE_THEME = IndustrialBlueTheme()


def industrial_application_palette(
    base_palette: QPalette | None = None,
    *,
    theme: IndustrialBlueTheme = INDUSTRIAL_BLUE_THEME,
) -> QPalette:
    """Build the application-wide light industrial palette.

    The working surfaces stay bright and readable while the navigation chrome is
    styled separately as deep navy. This keeps dialogs, tables and forms
    presentation-friendly instead of turning the whole desktop into a dark slab.
    """

    palette = QPalette(base_palette) if base_palette is not None else QPalette()
    role_colors = {
        QPalette.ColorRole.Window: theme.work_background,
        QPalette.ColorRole.WindowText: theme.text,
        QPalette.ColorRole.Base: theme.panel_background,
        QPalette.ColorRole.AlternateBase: theme.panel_alternate,
        QPalette.ColorRole.ToolTipBase: theme.panel_background,
        QPalette.ColorRole.ToolTipText: theme.text,
        QPalette.ColorRole.Text: theme.text,
        QPalette.ColorRole.Button: "#F5F9FC",
        QPalette.ColorRole.ButtonText: theme.text,
        QPalette.ColorRole.BrightText: theme.shell_text,
        QPalette.ColorRole.Light: theme.panel_background,
        QPalette.ColorRole.Midlight: "#D6E3EC",
        QPalette.ColorRole.Mid: theme.border,
        QPalette.ColorRole.Dark: "#6E8595",
        QPalette.ColorRole.Shadow: "#31495A",
        QPalette.ColorRole.Highlight: theme.accent,
        QPalette.ColorRole.HighlightedText: theme.shell_text,
        QPalette.ColorRole.Link: theme.accent_pressed,
        QPalette.ColorRole.LinkVisited: "#4869B1",
        QPalette.ColorRole.PlaceholderText: theme.muted_text,
    }
    for role, value in role_colors.items():
        palette.setColor(role, QColor(value))

    disabled = QPalette.ColorGroup.Disabled
    palette.setColor(disabled, QPalette.ColorRole.WindowText, QColor(theme.disabled_text))
    palette.setColor(disabled, QPalette.ColorRole.Text, QColor(theme.disabled_text))
    palette.setColor(disabled, QPalette.ColorRole.ButtonText, QColor(theme.disabled_text))
    palette.setColor(disabled, QPalette.ColorRole.Highlight, QColor(theme.border))
    palette.setColor(disabled, QPalette.ColorRole.HighlightedText, QColor(theme.muted_text))
    return palette


def industrial_shell_stylesheet(
    theme: IndustrialBlueTheme = INDUSTRIAL_BLUE_THEME,
) -> str:
    """Return the scoped navy/cyan shell layer for the main desktop window."""

    return f"""
/* DIGITAL GEOLOG industrial blue shell */
QMainWindow#mainWindow {{
    background: {theme.work_background};
    color: {theme.text};
}}
QMainWindow#mainWindow QMenuBar {{
    background: {theme.shell_background};
    color: {theme.shell_text};
    border-bottom: 1px solid {theme.shell_border};
}}
QMainWindow#mainWindow QMenuBar::item {{
    color: {theme.shell_text};
}}
QMainWindow#mainWindow QMenuBar::item:selected {{
    background: {theme.shell_surface_hover};
}}
QMainWindow#mainWindow QMenuBar::item:pressed {{
    background: {theme.accent};
    color: {theme.shell_text};
}}

QWidget#responsiveToolbarHost,
QFrame#mainToolbar {{
    background: {theme.shell_background};
    border-bottom: 1px solid {theme.shell_border};
}}
QFrame#mainToolbar QToolButton {{
    background: {theme.shell_surface};
    color: {theme.shell_text};
    border: 1px solid {theme.shell_border};
}}
QFrame#mainToolbar QToolButton:hover {{
    background: {theme.shell_surface_hover};
    border-color: {theme.accent_hover};
}}
QFrame#mainToolbar QToolButton:pressed,
QFrame#mainToolbar QToolButton:checked {{
    background: {theme.accent};
    border-color: {theme.accent_hover};
    color: {theme.shell_text};
}}
QFrame#mainToolbar QToolButton:disabled {{
    background: {theme.shell_background};
    border-color: {theme.shell_border};
    color: {theme.shell_disabled_text};
}}
QFrame#toolbarSeparator {{
    border-left-color: {theme.shell_border};
}}

QToolBar#leftPanelRail,
QToolBar#rightPanelRail {{
    background: {theme.shell_background};
}}
QToolBar#leftPanelRail {{
    border-right: 1px solid {theme.shell_border};
}}
QToolBar#rightPanelRail {{
    border-left: 1px solid {theme.shell_border};
}}
QToolBar#leftPanelRail QToolButton,
QToolBar#rightPanelRail QToolButton {{
    color: {theme.shell_text};
}}
QToolBar#leftPanelRail QToolButton:hover,
QToolBar#rightPanelRail QToolButton:hover {{
    background: {theme.shell_surface_hover};
    border-color: {theme.accent_hover};
}}
QToolBar#leftPanelRail QToolButton:checked,
QToolBar#rightPanelRail QToolButton:checked {{
    background: {theme.accent};
    border-color: {theme.accent_hover};
    color: {theme.shell_text};
}}

QTabWidget#workspaceTabs::pane {{
    background: {theme.panel_background};
    border-top: 1px solid {theme.border};
}}
QTabWidget#workspaceTabs QTabBar::tab {{
    background: {theme.panel_alternate};
    color: {theme.text};
    border-bottom-color: transparent;
}}
QTabWidget#workspaceTabs QTabBar::tab:hover {{
    background: {theme.selection};
}}
QTabWidget#workspaceTabs QTabBar::tab:selected {{
    background: {theme.panel_background};
    color: {theme.text};
    border-bottom-color: {theme.accent};
}}

QDockWidget::title {{
    background: {theme.panel_alternate};
    color: {theme.text};
    border-bottom: 1px solid {theme.border};
}}
QStatusBar#mainStatusBar {{
    background: {theme.shell_background};
    color: {theme.shell_text};
    border-top: 1px solid {theme.shell_border};
}}
QStatusBar#mainStatusBar QLabel,
QStatusBar#mainStatusBar QLabel#formWidthIndicator {{
    color: {theme.shell_text};
}}
QLabel#formWidthIndicator {{
    border-left-color: {theme.shell_border};
}}
"""


def wits0_dialog_stylesheet() -> str:
    """Return WITS-specific sizing for visible, operator-friendly scrollbars."""

    return """

QDialog#wits0CaptureDialog QScrollArea#wits0ScrollArea {
    border: 1px solid palette(mid);
    border-radius: 6px;
    background: palette(window);
}
QDialog#wits0CaptureDialog QWidget#wits0ScrollContent {
    background: palette(window);
}
QDialog#wits0CaptureDialog QScrollBar:vertical {
    width: 14px;
    margin: 2px;
    border: none;
    border-radius: 6px;
    background: palette(alternate-base);
}
QDialog#wits0CaptureDialog QScrollBar::handle:vertical {
    min-height: 34px;
    border: 1px solid palette(dark);
    border-radius: 5px;
    background: palette(mid);
}
QDialog#wits0CaptureDialog QScrollBar::handle:vertical:hover {
    border-color: palette(highlight);
    background: palette(highlight);
}
QDialog#wits0CaptureDialog QScrollBar::add-line:vertical,
QDialog#wits0CaptureDialog QScrollBar::sub-line:vertical {
    height: 0;
}
QDialog#wits0CaptureDialog QScrollBar::add-page:vertical,
QDialog#wits0CaptureDialog QScrollBar::sub-page:vertical {
    background: transparent;
}
QDialog#wits0CaptureDialog QScrollBar:horizontal {
    height: 14px;
    margin: 2px;
    border: none;
    border-radius: 6px;
    background: palette(alternate-base);
}
QDialog#wits0CaptureDialog QScrollBar::handle:horizontal {
    min-width: 34px;
    border: 1px solid palette(dark);
    border-radius: 5px;
    background: palette(mid);
}
QDialog#wits0CaptureDialog QScrollBar::handle:horizontal:hover {
    border-color: palette(highlight);
    background: palette(highlight);
}
QDialog#wits0CaptureDialog QScrollBar::add-line:horizontal,
QDialog#wits0CaptureDialog QScrollBar::sub-line:horizontal {
    width: 0;
}
QDialog#wits0CaptureDialog QScrollBar::add-page:horizontal,
QDialog#wits0CaptureDialog QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""


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
    color: palette(text);
    background: palette(alternate-base);
    border-color: palette(mid);
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
    color: palette(text);
    background: palette(alternate-base);
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

QMainWindow#mainWindow {
    background: palette(window);
    color: palette(window-text);
}
QMainWindow#mainWindow QMenuBar {
    min-height: 28px;
    padding: 2px 6px;
    border-bottom: 1px solid palette(mid);
    background: palette(window);
    color: palette(window-text);
}
QMainWindow#mainWindow QMenuBar::item {
    padding: 5px 9px;
    margin: 1px 2px;
    border-radius: 5px;
    background: transparent;
}
QMainWindow#mainWindow QMenuBar::item:selected {
    background: palette(midlight);
}
QMainWindow#mainWindow QMenuBar::item:pressed {
    background: palette(highlight);
    color: palette(highlighted-text);
}
QMainWindow#mainWindow QMenu {
    padding: 5px;
    border: 1px solid palette(mid);
    background: palette(base);
    color: palette(text);
}
QMainWindow#mainWindow QMenu::separator {
    height: 1px;
    margin: 5px 8px;
    background: palette(mid);
}

QWidget#responsiveToolbarHost {
    background: palette(window);
    border-bottom: 1px solid palette(mid);
}
QFrame#mainToolbar {
    min-height: 46px;
    border: none;
    border-bottom: 1px solid palette(mid);
    background: palette(window);
}
QFrame#mainToolbar QToolButton {
    min-height: 34px;
    padding: 5px 10px;
    border: 1px solid palette(mid);
    border-radius: 8px;
    color: palette(button-text);
    font-weight: 650;
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

QFrame#mainToolbar QToolButton:focus {
    border: 2px solid palette(highlight);
    padding: 4px 9px;
}
QFrame#mainToolbar QToolButton:disabled {
    color: palette(mid);
    background: palette(window);
    border-color: palette(mid);
}
QFrame#mainToolbar QToolButton#mainToolbarOverflowButton {
    min-width: 34px;
    padding-left: 7px;
    padding-right: 7px;
    font-size: 17px;
    font-weight: 700;
}
QFrame#toolbarSeparator {
    background: transparent;
    border: none;
    border-left: 1px solid palette(mid);
    margin: 5px 3px;
}

QToolBar#leftPanelRail,
QToolBar#rightPanelRail {
    spacing: 5px;
    padding: 5px 4px;
    border: none;
    background: palette(window);
}
QToolBar#leftPanelRail {
    border-right: 1px solid palette(mid);
}
QToolBar#rightPanelRail {
    border-left: 1px solid palette(mid);
}
QToolBar#leftPanelRail QToolButton,
QToolBar#rightPanelRail QToolButton {
    min-width: 32px;
    min-height: 32px;
    padding: 3px;
    border: 1px solid transparent;
    border-radius: 7px;
    color: palette(button-text);
    background: transparent;
}
QToolBar#leftPanelRail QToolButton:hover,
QToolBar#rightPanelRail QToolButton:hover {
    border-color: palette(mid);
    background: palette(midlight);
}
QToolBar#leftPanelRail QToolButton:checked,
QToolBar#rightPanelRail QToolButton:checked {
    border-color: palette(highlight);
    background: palette(highlight);
    color: palette(highlighted-text);
}

QTabWidget#workspaceTabs::pane {
    border: none;
    border-top: 1px solid palette(mid);
    background: palette(base);
}
QTabWidget#workspaceTabs QTabBar::tab {
    min-height: 32px;
    padding: 6px 13px;
    margin: 0 1px 0 0;
    border: 1px solid transparent;
    border-bottom: 3px solid transparent;
    background: palette(window);
    color: palette(window-text);
}
QTabWidget#workspaceTabs QTabBar::tab:hover {
    background: palette(midlight);
}
QTabWidget#workspaceTabs QTabBar::tab:selected {
    border-bottom-color: palette(highlight);
    background: palette(base);
    color: palette(text);
    font-weight: 700;
}
QTabWidget#workspaceTabs QTabBar::tab:disabled {
    color: palette(mid);
}

QDockWidget {
    color: palette(window-text);
}
QDockWidget::title {
    min-height: 24px;
    padding: 5px 8px;
    border-bottom: 1px solid palette(mid);
    background: palette(alternate-base);
    color: palette(window-text);
    font-weight: 650;
    text-align: left;
}
QDockWidget::close-button,
QDockWidget::float-button {
    border: none;
    border-radius: 4px;
    background: transparent;
}
QDockWidget::close-button:hover,
QDockWidget::float-button:hover {
    background: palette(midlight);
}

QStatusBar#mainStatusBar {
    min-height: 24px;
    padding: 1px 6px;
    border-top: 1px solid palette(mid);
    background: palette(window);
    color: palette(window-text);
}
QStatusBar#mainStatusBar QLabel {
    color: palette(window-text);
}
QLabel#formWidthIndicator {
    min-height: 20px;
    padding: 1px 8px;
    border-left: 1px solid palette(mid);
    color: palette(window-text);
}
QStackedWidget#centralWorkspaceStack,
QWidget#workspaceShell {
    background: palette(base);
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

QLabel#logo-catalog-preview {
    background: palette(base);
    border: 1px solid palette(mid);
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
    color: palette(text);
    background: palette(alternate-base);
    border-color: palette(mid);
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
    """Install the shared industrial-blue palette and presentation contract once."""

    if bool(app.property(_ADAPTIVE_STYLE_PROPERTY)):
        return
    app.setPalette(industrial_application_palette(app.palette()))
    current = app.styleSheet().rstrip()
    shared = adaptive_application_stylesheet().strip()
    shell = industrial_shell_stylesheet().strip()
    wits0 = wits0_dialog_stylesheet().strip()
    combined = f"{shared}\n{shell}\n{wits0}"
    app.setStyleSheet(f"{current}\n{combined}" if current else combined)
    app.setProperty(_ADAPTIVE_STYLE_PROPERTY, True)


__all__ = [
    "INDUSTRIAL_BLUE_THEME",
    "IndustrialBlueTheme",
    "adaptive_application_stylesheet",
    "apply_adaptive_application_style",
    "industrial_application_palette",
    "industrial_shell_stylesheet",
    "wits0_dialog_stylesheet",
]
