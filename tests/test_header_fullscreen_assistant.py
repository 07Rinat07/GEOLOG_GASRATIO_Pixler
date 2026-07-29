from __future__ import annotations

import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from geoworkbench.domain.models import MasterlogHeaderElement
from geoworkbench.importers.skf_importer import _normalize_shape_geometry
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.header_visual_assistant import HeaderVisualAssistant


def _application() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return cast(QApplication, existing)
    return QApplication([])


def test_skf_wide_separator_is_normalized_to_editable_horizontal_line() -> None:
    kind, width, height = _normalize_shape_geometry(139.0, 18.0, "unknown")

    assert kind == "horizontal"
    assert width == 139.0
    assert height == 0.1


def test_skf_tall_separator_is_normalized_to_editable_vertical_line() -> None:
    kind, width, height = _normalize_shape_geometry(18.0, 139.0, "unknown")

    assert kind == "vertical"
    assert width == 0.1
    assert height == 139.0


def test_explicit_skf_diagonal_and_rectangular_frame_are_preserved() -> None:
    assert _normalize_shape_geometry(40.0, 20.0, "diagonal") == (
        "diagonal",
        40.0,
        20.0,
    )
    assert _normalize_shape_geometry(40.0, 20.0, "unknown") == (
        "frame",
        40.0,
        20.0,
    )


def test_visual_assistant_warns_about_printed_diagonal_and_exposes_fix_actions() -> None:
    _application()
    assistant = HeaderVisualAssistant(language=AppLanguage.RU)
    diagonal = MasterlogHeaderElement(
        element_id="line-1",
        element_type="line",
        x_mm=6.0,
        y_mm=11.0,
        width_mm=139.0,
        height_mm=18.0,
        properties={"source_component": "TPrintShape1"},
    )
    requested: list[str] = []
    assistant.line_orientation_requested.connect(requested.append)

    assistant.set_element(
        diagonal,
        page_width_mm=285.0,
        header_height_mm=60.0,
    )
    assistant.horizontal_button.click()
    assistant.vertical_button.click()

    assert "диагонал" in assistant.warning.text().casefold()
    assert not assistant.line_row.isHidden()
    assert requested == ["horizontal", "vertical"]
    assistant.close()


def test_visual_assistant_quick_text_action_emits_current_value() -> None:
    _application()
    assistant = HeaderVisualAssistant(language=AppLanguage.RU)
    text_element = MasterlogHeaderElement(
        element_id="text-1",
        element_type="text",
        x_mm=10.0,
        y_mm=5.0,
        width_mm=50.0,
        height_mm=5.0,
        properties={"text": "Исходный текст"},
    )
    emitted: list[str] = []
    assistant.text_requested.connect(emitted.append)

    assistant.set_element(
        text_element,
        page_width_mm=285.0,
        header_height_mm=60.0,
    )
    assistant.quick_text.setText("Новый текст")
    assistant.apply_text_button.click()

    assert not assistant.text_row.isHidden()
    assert emitted == ["Новый текст"]
    assistant.close()
