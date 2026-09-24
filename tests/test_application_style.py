from __future__ import annotations

import importlib.util

import pytest

from geoworkbench.ui.application_style import adaptive_application_stylesheet


def test_adaptive_application_stylesheet_uses_palette_roles_and_no_fixed_widths() -> None:
    stylesheet = adaptive_application_stylesheet()

    assert 'QPushButton[uiRole="primary"]' in stylesheet
    assert 'QPushButton[uiRole="destructive"]' in stylesheet
    assert "palette(highlight)" in stylesheet
    assert "min-height: 28px" in stylesheet
    assert "\n    width:" not in stylesheet


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
