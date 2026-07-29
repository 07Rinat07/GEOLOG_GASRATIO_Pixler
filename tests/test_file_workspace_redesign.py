from __future__ import annotations

from pathlib import Path

import fitz
from PySide6.QtWidgets import QApplication, QFrame, QTabWidget

from geoworkbench.ui.file_workspace_production import FileWorkspaceWidget


def _application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _select_data(combo, value: str) -> None:
    index = combo.findData(value)
    assert index >= 0, value
    combo.setCurrentIndex(index)


def _write_pdf(path: Path, pages: int = 2) -> None:
    document = fitz.open()
    try:
        for page_number in range(pages):
            page = document.new_page()
            page.insert_text((72, 72), f"PAGE {page_number + 1}")
        document.save(path)
    finally:
        document.close()


def test_modern_workspace_is_discoverable_and_has_command_bar() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")

    assert widget.objectName() == "modernFileWorkspace"
    assert widget.tab_title("ru") == "Файлы / PDF / Калькулятор"
    assert widget.sections.tabPosition() == QTabWidget.TabPosition.North
    assert widget.findChild(QFrame, "filesHeader") is not None
    assert widget.findChild(QFrame, "commandBar") is not None
    assert widget.findChild(QFrame, "contextBar") is not None

    widget.deleteLater()


def test_calculator_and_converter_update_live_without_stale_result() -> None:
    application = _application()
    widget = FileWorkspaceWidget(language="ru")

    widget.expression_input.setText("sqrt(144) + 2 1/2")
    application.processEvents()
    assert widget.expression_result.text() == "14.5"

    _select_data(widget.converter_category, "volume")
    application.processEvents()
    _select_data(widget.converter_source, "ml")
    _select_data(widget.converter_target, "l")
    widget.converter_value.setText("7 1/2")
    application.processEvents()
    widget._convert_units_live()

    assert widget.converter_result.text() == "0.0075"
    assert "7.5 мл" in widget._converter_equation.text()
    assert "0.0075 л" in widget._converter_equation.text()

    _select_data(widget.converter_source, "l")
    _select_data(widget.converter_target, "ml")
    application.processEvents()
    widget._convert_units_live()
    assert widget.converter_result.text() == "7500"

    widget.deleteLater()


def test_pdf_page_sidebar_and_context_tools_follow_document_type(tmp_path: Path) -> None:
    _application()
    source = tmp_path / "two-pages.pdf"
    _write_pdf(source)
    widget = FileWorkspaceWidget(language="ru")

    widget.document_service.open(source)
    widget._refresh_document()

    assert widget._page_list.count() == 2
    assert widget._page_list.currentRow() == 0
    assert all(button.isEnabled() for button in widget._pdf_tools)
    assert all(not button.isEnabled() for button in widget._image_tools)
    assert widget.document_service.page_index == 0

    widget._page_list.setCurrentRow(1)
    assert widget.document_service.page_index == 1
    assert widget.page_label.text() == "Страница 2 / 2"

    widget.deleteLater()
