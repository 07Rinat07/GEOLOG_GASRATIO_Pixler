from __future__ import annotations

import importlib.util
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
    assert "palette(highlight)" in stylesheet
    assert "palette(base)" in stylesheet
    assert "min-height: 28px" in stylesheet
    assert "\n    width:" not in stylesheet
    assert "#" not in stylesheet


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
