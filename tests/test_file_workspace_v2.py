from __future__ import annotations

from pathlib import Path

import fitz
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QFrame, QToolButton

from geoworkbench.files.enhanced_document_service import EnhancedDocumentService
from geoworkbench.ui.file_workspace_i18n import catalogs_have_same_keys
from geoworkbench.ui.file_workspace_v2 import FileWorkspaceWidget


def _application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _sample_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=300, height=220)
    page.insert_text((30, 70), "DELETE THIS TEXT", fontsize=18)
    document.save(path)
    document.close()
    return path


def test_translation_catalogs_have_identical_keys() -> None:
    assert catalogs_have_same_keys()


def test_workspace_is_localized_in_all_three_languages() -> None:
    _application()
    expected = {
        "ru": ("Документы", "▣ Ластик"),
        "kk": ("Құжаттар", "▣ Өшіргіш"),
        "en": ("Documents", "▣ Eraser"),
    }
    for language, (tab, eraser) in expected.items():
        widget = FileWorkspaceWidget(language=language)
        assert widget.sections.tabText(0) == tab
        button = widget.findChild(QToolButton, "pdfBrushEraserButton")
        assert button is not None
        assert button.text() == eraser
        assert len(widget.findChildren(QFrame, "expertHelpCard")) == 5
        widget.deleteLater()


def test_eraser_is_separate_visible_checkable_tool() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")
    eraser = widget.findChild(QToolButton, "pdfBrushEraserButton")
    text_button = widget.findChild(QToolButton, "pdfFormattedTextButton")
    replace_button = widget.findChild(QToolButton, "pdfReplaceTextButton")
    assert eraser is not None and eraser.isCheckable()
    assert text_button is not None and text_button is not eraser
    assert replace_button is not None and replace_button is not eraser
    assert "замен" not in eraser.text().casefold()
    assert widget.eraser_size.minimum() <= 12
    assert widget.eraser_size.maximum() >= 120
    widget.deleteLater()


def test_calculator_fields_are_wide_and_have_help() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")
    assert widget.expression_input.minimumWidth() >= 440
    assert widget.expression_result.minimumWidth() >= 300
    assert widget.converter_value.minimumWidth() >= 220
    assert widget.converter_result.minimumWidth() >= 300
    assert widget.expression_input.placeholderText()
    assert widget.eraser_button.toolTip()
    widget.deleteLater()


def test_brush_eraser_removes_pdf_content_in_one_undo_step(tmp_path: Path) -> None:
    source = _sample_pdf(tmp_path / "source.pdf")
    service = EnhancedDocumentService()
    service.open(source)
    service.erase_pdf_rects([(20, 40, 250, 90)])
    assert service.can_undo
    assert "DELETE THIS TEXT" not in service._pdf_page().get_text()
    service.undo()
    assert "DELETE THIS TEXT" in service._pdf_page().get_text()


def test_styled_text_can_be_inserted(tmp_path: Path) -> None:
    source = _sample_pdf(tmp_path / "styled.pdf")
    service = EnhancedDocumentService()
    service.open(source)
    service.add_styled_pdf_text(
        (20, 100, 280, 160),
        "Formatted replacement",
        fontname="hebi",
        font_size=14,
        color=(0.1, 0.2, 0.7),
        alignment=1,
        background=(0.9, 0.9, 0.5),
        replace=False,
    )
    assert "Formatted replacement" in service._pdf_page().get_text()


def test_overlay_accepts_visible_brush_points() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")
    overlay = widget._eraser_overlay
    overlay.set_active(True)
    overlay.set_brush_size(48)
    assert not overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert overlay._distance(QPointF(0, 0), QPointF(3, 4)) == 5
    widget.deleteLater()
