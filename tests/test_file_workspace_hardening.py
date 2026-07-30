from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz
from PIL import Image
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QTabWidget, QWidget

from geoworkbench.files.document_service import DocumentError
from geoworkbench.files.enhanced_document_service import EnhancedDocumentService
from geoworkbench.ui.file_workspace_hardening import (
    FileWorkspaceWidget,
    _ContinuousEraserOverlay,
)


def _application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _sample_pdf(path: Path, text: str = "DELETE THIS TEXT") -> Path:
    document = fitz.open()
    page = document.new_page(width=300, height=220)
    page.insert_text((30, 70), text, fontsize=18)
    document.save(path)
    document.close()
    return path


def _rotated_pdf(path: Path) -> tuple[Path, fitz.Rect]:
    document = fitz.open()
    page = document.new_page(width=240, height=140)
    page.insert_text((35, 75), "ROTATED TARGET", fontsize=18)
    target = page.search_for("ROTATED TARGET")[0]
    page.set_rotation(90)
    visible = target * page.rotation_matrix
    visible = fitz.Rect(
        visible.x0 - 3,
        visible.y0 - 3,
        visible.x1 + 3,
        visible.y1 + 3,
    )
    document.save(path)
    document.close()
    return path, visible


def test_interpolated_eraser_has_no_gaps_larger_than_half_brush() -> None:
    _application()
    parent = QWidget()
    overlay = _ContinuousEraserOverlay(parent)
    overlay.set_brush_size(20)
    overlay._points = [QPointF(0.0, 0.0)]
    overlay._append_interpolated(QPointF(100.0, 0.0))

    distances = [
        overlay._distance(left, right)
        for left, right in zip(overlay._points, overlay._points[1:], strict=True)
    ]
    assert distances
    assert max(distances) <= 10.01
    parent.deleteLater()


def test_rotated_pdf_eraser_derotates_visible_coordinates(tmp_path: Path) -> None:
    source, visible = _rotated_pdf(tmp_path / "rotated.pdf")
    service = EnhancedDocumentService()
    service.open(source)

    service.erase_pdf_display_rects(
        [(visible.x0, visible.y0, visible.x1, visible.y1)]
    )

    assert "ROTATED TARGET" not in service._pdf_page().get_text()
    assert service.can_undo
    service.undo()
    assert "ROTATED TARGET" in service._pdf_page().get_text()


def test_failed_text_replacement_restores_document_and_history(tmp_path: Path) -> None:
    source = _sample_pdf(tmp_path / "transaction.pdf", "ORIGINAL CONTENT")
    service = EnhancedDocumentService()
    service.open(source)

    with pytest.raises(DocumentError, match="Текст не помещается"):
        service.add_styled_pdf_text(
            (20, 40, 90, 46),
            "A very long replacement that cannot fit into this tiny rectangle",
            fontname="helv",
            font_size=72,
            color=(0.0, 0.0, 0.0),
            alignment=0,
            background=(1.0, 1.0, 0.0),
            replace=True,
        )

    assert "ORIGINAL CONTENT" in service._pdf_page().get_text()
    assert not service.can_undo
    assert not service.can_redo
    service.redo()
    assert "ORIGINAL CONTENT" in service._pdf_page().get_text()


def test_eraser_deactivates_when_an_image_is_opened(tmp_path: Path) -> None:
    _application()
    pdf = _sample_pdf(tmp_path / "source.pdf")
    image = tmp_path / "source.png"
    Image.new("RGB", (120, 80), "white").save(image)

    widget = FileWorkspaceWidget(language="ru")
    widget.document_service.open(pdf)
    widget._refresh_document()
    widget.eraser_button.setChecked(True)
    assert widget._eraser_overlay._active

    widget.document_service.open(image)
    widget._refresh_document()

    assert not widget.eraser_button.isChecked()
    assert not widget._eraser_overlay._active
    widget.close()
    widget.deleteLater()


def test_text_overflow_error_is_localized() -> None:
    _application()
    source = "Текст не помещается: увеличьте область или уменьшите размер шрифта"
    english = FileWorkspaceWidget(language="en")
    kazakh = FileWorkspaceWidget(language="kk")

    assert english._localized_error(source).startswith("The text does not fit")
    assert kazakh._localized_error(source).startswith("Мәтін сыймайды")

    english.deleteLater()
    kazakh.deleteLater()


def test_language_action_rebuilds_workspace_and_preserves_state(tmp_path: Path) -> None:
    application = _application()
    source = _sample_pdf(tmp_path / "language.pdf")
    window = QMainWindow()
    tabs = QTabWidget(window)
    window.setCentralWidget(tabs)
    action = QAction(window)
    window.language = SimpleNamespace(value="ru")
    window.language_actions = {"en": action}

    widget = FileWorkspaceWidget(tabs, language="ru")
    tabs.addTab(widget, widget.tab_title("ru"))
    window.file_workspace = widget
    widget.document_service.open(source)
    widget._refresh_document()
    widget.expression_input.setText("sqrt(144) + 2 1/2")
    original_service = widget.document_service
    window.show()
    application.processEvents()
    widget._install_language_sync()

    window.language = SimpleNamespace(value="en")
    action.trigger()
    application.processEvents()
    application.processEvents()

    replacement = window.file_workspace
    assert replacement is not widget
    assert replacement.language == "en"
    assert replacement.document_service is original_service
    assert replacement.expression_input.text() == "sqrt(144) + 2 1/2"
    assert tabs.tabText(0) == "Files / PDF / Calculator"
    title = replacement.findChild(QLabel, "filesTitle")
    assert title is not None and title.text().startswith("Files")

    window.close()
    window.deleteLater()
