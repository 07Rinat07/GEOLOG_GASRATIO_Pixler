from __future__ import annotations

from pathlib import Path

import fitz
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QToolButton

from geoworkbench.files.enhanced_document_service import EnhancedDocumentService
from geoworkbench.ui.file_workspace_geometry import eraser_stroke_rectangles
from geoworkbench.ui.file_workspace_i18n import catalogs_have_same_keys
from geoworkbench.ui.file_workspace_release import FileWorkspaceWidget


def _application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _dispose(widget: FileWorkspaceWidget) -> None:
    widget.close()
    widget.deleteLater()
    _application().processEvents()


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
        _dispose(widget)


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
    _dispose(widget)


def test_calculator_fields_are_wide_and_have_help() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")
    assert widget.expression_input.minimumWidth() >= 440
    assert widget.expression_result.minimumWidth() >= 300
    assert widget.converter_value.minimumWidth() >= 220
    assert widget.converter_result.minimumWidth() >= 300
    assert widget.expression_input.placeholderText()
    assert widget.eraser_button.toolTip()
    _dispose(widget)


def test_logo_help_card_is_inside_controls_not_a_side_column() -> None:
    _application()
    widget = FileWorkspaceWidget(language="en")
    page = widget.sections.widget(2)
    card = page.findChild(QFrame, "expertHelpCard") if page is not None else None
    assert card is not None
    assert card.parentWidget() is widget.logo_text.parentWidget()
    _dispose(widget)


def test_english_page_label_datum_hint_and_units_are_localized(tmp_path: Path) -> None:
    _application()
    source = _sample_pdf(tmp_path / "english-ui.pdf")
    widget = FileWorkspaceWidget(language="en")
    widget.document_service.open(source)
    widget._refresh_document()
    assert widget.page_label.text() == "Page 1 / 1"

    datum_group = widget.datum_inputs[0].parentWidget()
    datum_hints = [
        label.text()
        for label in datum_group.findChildren(QLabel)
        if label.objectName() == "hint"
    ] if datum_group is not None else []
    assert any(text.startswith("Chain:") for text in datum_hints)
    assert all("Цепочка" not in text for text in datum_hints)

    volume_index = widget.converter_category.findData("volume")
    widget.converter_category.setCurrentIndex(volume_index)
    assert widget.converter_category.currentText() == "Volume"
    assert widget.converter_source.itemText(widget.converter_source.findData("ml")) == "mL"
    assert widget.converter_target.itemText(widget.converter_target.findData("l")) == "L"
    assert widget.pipe_wall_mm.suffix() == " mm"
    assert widget.drill_flow.suffix() == " L/s"
    _dispose(widget)


def test_brush_eraser_removes_pdf_content_in_one_undo_step(tmp_path: Path) -> None:
    source = _sample_pdf(tmp_path / "source.pdf")
    service = EnhancedDocumentService()
    service.open(source)
    service.erase_pdf_rects([(20, 40, 250, 90)])
    assert service.can_undo
    assert "DELETE THIS TEXT" not in service._pdf_page().get_text()
    service.undo()
    assert "DELETE THIS TEXT" in service._pdf_page().get_text()


def test_brush_eraser_result_persists_after_save(tmp_path: Path) -> None:
    source = _sample_pdf(tmp_path / "eraser-source.pdf")
    target = tmp_path / "eraser-result.pdf"
    service = EnhancedDocumentService()
    service.open(source)
    service.erase_pdf_rects([(20, 40, 250, 90)])
    service.save_as(target)

    with fitz.open(target) as saved:
        assert "DELETE THIS TEXT" not in saved[0].get_text()


def test_visible_brush_coordinates_match_pdf_at_non_default_zoom(tmp_path: Path) -> None:
    source = _sample_pdf(tmp_path / "zoomed-brush.pdf")
    points = [QPointF(float(x), 140.0) for x in range(60, 461, 30)]
    rects = eraser_stroke_rectangles(points, brush_size_px=70, render_scale=2.0)
    assert rects[0] == (12.5, 52.5, 47.5, 87.5)

    service = EnhancedDocumentService()
    service.open(source)
    service.erase_pdf_rects(rects)
    assert "DELETE THIS TEXT" not in service._pdf_page().get_text()
    assert service.can_undo
    service.undo()
    assert "DELETE THIS TEXT" in service._pdf_page().get_text()


def test_styled_unicode_text_persists_after_save(tmp_path: Path) -> None:
    source = _sample_pdf(tmp_path / "styled-source.pdf")
    target = tmp_path / "styled-result.pdf"
    inserted = "Русский Қазақша ӘҒҚҢӨҰҮҺІ"
    service = EnhancedDocumentService()
    service.open(source)
    service.add_styled_pdf_text(
        (20, 100, 280, 175),
        inserted,
        fontname="hebi",
        font_size=14,
        color=(0.1, 0.2, 0.7),
        alignment=1,
        background=(0.9, 0.9, 0.5),
        replace=False,
    )
    service.save_as(target)

    with fitz.open(target) as saved:
        assert inserted in saved[0].get_text()
        assert any(font[5] == "Identity-H" for font in saved.get_page_fonts(0))


def test_overlay_accepts_visible_brush_points() -> None:
    _application()
    widget = FileWorkspaceWidget(language="ru")
    overlay = widget._eraser_overlay
    overlay.set_active(True)
    overlay.set_brush_size(48)
    assert not overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert overlay._distance(QPointF(0, 0), QPointF(3, 4)) == 5
    _dispose(widget)
