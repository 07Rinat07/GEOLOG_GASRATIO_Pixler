from __future__ import annotations

import re
from pathlib import Path

from geoworkbench.ui.interpretation_report_workspace_guidance import (
    _interpretation_workspace_accessibility_stylesheet,
)


def test_interpretation_workspace_readability_style_is_palette_aware() -> None:
    stylesheet = _interpretation_workspace_accessibility_stylesheet()

    assert "QWidget#interpretation-report-workspace QLabel" in stylesheet
    assert "color: palette(window-text)" in stylesheet
    assert "QWidget#interpretation-report-workspace QPushButton" in stylesheet
    assert "border-radius: 8px" in stylesheet
    assert "QScrollBar:vertical" in stylesheet
    assert "QScrollBar:horizontal" in stylesheet
    assert "QScrollBar::handle:vertical:hover" in stylesheet
    assert "QScrollBar::handle:horizontal:hover" in stylesheet
    assert re.search(r"#[0-9a-fA-F]{3,8}\\b", stylesheet) is None


def test_gas_context_entry_button_keeps_text_visible_from_the_left() -> None:
    stylesheet = _interpretation_workspace_accessibility_stylesheet()
    selector = "QPushButton#gas-context-event-editor-button"
    block = stylesheet.split(selector, 1)[1].split("}", 1)[0]

    assert "min-height: 52px" in block
    assert "padding-left: 16px" in block
    assert "padding-right: 12px" in block
    assert "text-align: left" in block
    assert "color: palette(button-text)" in block
    assert "border-left: 4px solid palette(highlight)" in block


def test_interpretation_sidebar_no_longer_uses_narrow_fixed_width() -> None:
    source = Path(
        "src/geoworkbench/ui/interpretation_report_workspace_layout.py"
    ).read_text(encoding="utf-8")
    guidance = Path(
        "src/geoworkbench/ui/interpretation_report_workspace_guidance.py"
    ).read_text(encoding="utf-8")

    assert "setFixedWidth(196)" not in source
    assert "preview_sidebar.setMinimumWidth(224)" in source
    assert "preview_sidebar.setMaximumWidth(264)" in source
    assert '"1. Газовые события\\nперед расчётом…"' in guidance
    assert '"1. Gas events before\\ncalculation…"' in guidance
