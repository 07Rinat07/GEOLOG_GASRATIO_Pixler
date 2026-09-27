from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from geoworkbench.ui.application_style import (
    INDUSTRIAL_BLUE_THEME,
    adaptive_application_stylesheet,
    industrial_application_palette,
    industrial_shell_stylesheet,
    wits0_dialog_stylesheet,
)


def test_adaptive_application_stylesheet_uses_palette_roles_and_no_fixed_widths() -> None:
    stylesheet = adaptive_application_stylesheet()

    assert 'QPushButton[uiRole="primary"]' in stylesheet
    assert 'QPushButton[uiRole="secondary"]' in stylesheet
    assert 'QPushButton[uiRole="destructive"]' in stylesheet
    assert "QLineEdit:read-only" in stylesheet
    assert "QToolTip" in stylesheet
    assert "QMainWindow#mainWindow" in stylesheet
    assert "QFrame#mainToolbar" in stylesheet
    assert "QToolBar#leftPanelRail" in stylesheet
    assert "QToolBar#rightPanelRail" in stylesheet
    assert "QTabWidget#workspaceTabs" in stylesheet
    assert "QStatusBar#mainStatusBar" in stylesheet
    assert "QDockWidget::title" in stylesheet
    assert "QFrame#formEditToolbar" in stylesheet
    assert "QLabel#formEditToolbarCaption" in stylesheet
    assert "QPushButton#print-center-primary-action" in stylesheet
    assert "QLabel#print-center-header-preview" in stylesheet
    assert "QLabel#print-center-depth-standard" in stylesheet
    assert "QLabel#logo-catalog-preview" in stylesheet
    assert 'QLabel#print-job-status-title[statusRole="success"]' in stylesheet
    assert 'QLabel#print-job-status-title[statusRole="error"]' in stylesheet
    assert 'QLabel[validationRole="error"]' in stylesheet
    assert 'QLabel[validationRole="warning"]' in stylesheet
    assert 'QLabel[validationRole="success"]' in stylesheet
    assert 'QLabel[guidanceRole="info"]' in stylesheet
    assert 'QLabel[guidanceRole="warning"]' in stylesheet
    assert "QLabel#depth-annotations-editor-hint" in stylesheet
    assert "QLabel#depth-annotations-layer-title" in stylesheet
    assert "QLabel#depth-annotations-axis-display" in stylesheet
    assert "QLabel#depth-annotations-drag-hint" in stylesheet
    assert "QLabel#las-editor-title" in stylesheet
    assert "QLabel#las-editor-summary" in stylesheet
    assert "QLabel#las-editor-safety-note" in stylesheet
    info_block = stylesheet.split('QLabel[guidanceRole="info"]', 1)[1].split("}", 1)[0]
    assert "color: palette(window-text)" in info_block
    assert "color: palette(mid)" not in info_block
    assert "QDialog#form-create-dialog QTreeWidget::item" in stylesheet
    assert "QDialog#form-manager-dialog QTreeWidget::item" in stylesheet
    assert "QLabel#form-manager-heading" in stylesheet
    assert 'QLabel[hintRole="success"]' in stylesheet
    assert 'QLabel[hintRole="warning"]' in stylesheet
    assert 'QLabel[hintRole="error"]' in stylesheet
    assert 'QLabel[hintRole="neutral"]' in stylesheet
    assert "palette(highlight)" in stylesheet
    assert "palette(base)" in stylesheet
    assert "min-height: 28px" in stylesheet
    assert "\n    width:" not in stylesheet
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", stylesheet) is None


def test_logo_catalog_preview_uses_shared_palette_style() -> None:
    source = Path("src/geoworkbench/ui/logo_catalog_dialog.py").read_text(encoding="utf-8")

    assert 'self.preview.setObjectName("logo-catalog-preview")' in source
    assert "self.preview.setStyleSheet(" not in source
    assert "background: white" not in source
    assert "#cbd5e1" not in source


def test_entrypoint_does_not_override_global_palette_or_tooltip_style() -> None:
    source = Path("src/geoworkbench/app/main.py").read_text(encoding="utf-8")

    assert "_configure_readable_tooltips" not in source
    assert "QColor" not in source
    assert "QPalette" not in source
    assert ".setPalette(" not in source
    assert ".setStyleSheet(" not in source


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed",
)
def test_industrial_application_palette_uses_bright_work_surfaces_and_blue_accent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    palette = industrial_application_palette(app.palette())

    assert palette.color(QPalette.ColorRole.Window).name().upper() == "#EDF4F8"
    assert palette.color(QPalette.ColorRole.Base).name().upper() == "#FFFFFF"
    assert palette.color(QPalette.ColorRole.Text).name().upper() == "#122B3E"
    assert palette.color(QPalette.ColorRole.Highlight).name().upper() == "#00A6E2"
    assert palette.color(QPalette.ColorRole.Window).lightness() > 200
    assert palette.color(QPalette.ColorRole.Base).lightness() > 240


def test_industrial_shell_stylesheet_uses_navy_navigation_and_cyan_activity() -> None:
    stylesheet = industrial_shell_stylesheet()

    assert f"background: {INDUSTRIAL_BLUE_THEME.shell_background}" in stylesheet
    assert f"background: {INDUSTRIAL_BLUE_THEME.accent}" in stylesheet
    assert f"background: {INDUSTRIAL_BLUE_THEME.panel_background}" in stylesheet
    assert INDUSTRIAL_BLUE_THEME.shell_disabled_text == "#8EADC2"
    assert "QMainWindow#mainWindow QMenuBar" in stylesheet
    assert "QFrame#mainToolbar" in stylesheet
    assert "QToolBar#leftPanelRail" in stylesheet
    assert "QStatusBar#mainStatusBar" in stylesheet


def test_wits0_dialog_stylesheet_scopes_visible_scrollbar_dimensions() -> None:
    stylesheet = wits0_dialog_stylesheet()

    assert "QDialog#wits0CaptureDialog QScrollBar:vertical" in stylesheet
    assert "QDialog#wits0CaptureDialog QScrollBar:horizontal" in stylesheet
    assert "width: 14px" in stylesheet
    assert "height: 14px" in stylesheet
    assert "min-height: 34px" in stylesheet
    assert "min-width: 34px" in stylesheet


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None,
    reason="PySide6 is not installed",
)
def test_adaptive_application_style_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from geoworkbench.ui.application_style import apply_adaptive_application_style

    app = QApplication.instance() or QApplication([])
    original = app.styleSheet()
    original_palette = app.palette()
    try:
        apply_adaptive_application_style(app)
        first = app.styleSheet()
        apply_adaptive_application_style(app)
        second = app.styleSheet()

        assert first == second
        assert adaptive_application_stylesheet().strip() in first
        assert industrial_shell_stylesheet().strip() in first
        assert wits0_dialog_stylesheet().strip() in first
    finally:
        app.setStyleSheet(original)
        app.setPalette(original_palette)
        app.setProperty("_geologAdaptiveUiInstalled", False)
