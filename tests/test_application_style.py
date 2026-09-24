from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from geoworkbench.ui.application_style import adaptive_application_stylesheet


def test_adaptive_application_stylesheet_uses_palette_roles_and_no_fixed_widths() -> None:
    stylesheet = adaptive_application_stylesheet()

    assert 'QPushButton[uiRole="primary"]' in stylesheet
    assert 'QPushButton[uiRole="secondary"]' in stylesheet
    assert 'QPushButton[uiRole="destructive"]' in stylesheet
    assert "QLineEdit:read-only" in stylesheet
    assert "QToolTip" in stylesheet
    assert "QFrame#mainToolbar" in stylesheet
    assert "QFrame#formEditToolbar" in stylesheet
    assert "QLabel#formEditToolbarCaption" in stylesheet
    assert "QPushButton#print-center-primary-action" in stylesheet
    assert "QLabel#print-center-header-preview" in stylesheet
    assert "QLabel#print-center-depth-standard" in stylesheet
    assert 'QLabel#print-job-status-title[statusRole="success"]' in stylesheet
    assert 'QLabel#print-job-status-title[statusRole="error"]' in stylesheet
    assert 'QLabel[validationRole="error"]' in stylesheet
    assert "palette(highlight)" in stylesheet
    assert "palette(base)" in stylesheet
    assert "min-height: 28px" in stylesheet
    assert "\n    width:" not in stylesheet
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", stylesheet) is None


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
def test_adaptive_application_style_preserves_dark_application_palette(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    from geoworkbench.ui.application_style import apply_adaptive_application_style

    app = QApplication.instance() or QApplication([])
    original_style = app.styleSheet()
    original_palette = app.palette()
    original_installed = app.property("_geologAdaptiveUiInstalled")
    dark_palette = QPalette(original_palette)
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(24, 24, 24))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(232, 232, 232))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(32, 32, 32))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
    app.setPalette(dark_palette)
    app.setProperty("_geologAdaptiveUiInstalled", False)
    before = app.palette()

    try:
        apply_adaptive_application_style(app)
        after = app.palette()

        for role in (
            QPalette.ColorRole.Window,
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Base,
            QPalette.ColorRole.Text,
        ):
            assert after.color(role) == before.color(role)
    finally:
        app.setStyleSheet(original_style)
        app.setPalette(original_palette)
        app.setProperty("_geologAdaptiveUiInstalled", original_installed)


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
    try:
        apply_adaptive_application_style(app)
        first = app.styleSheet()
        apply_adaptive_application_style(app)
        second = app.styleSheet()

        assert first == second
        assert adaptive_application_stylesheet().strip() in first
    finally:
        app.setStyleSheet(original)
        app.setProperty("_geologAdaptiveUiInstalled", False)
