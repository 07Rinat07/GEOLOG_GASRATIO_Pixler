"""Actual Qt report-preview authoring and PDF export regressions."""

from pathlib import Path

import fitz
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QInputDialog

from geoworkbench.services.localization import AppLanguage
from geoworkbench.printing.report_preview_overlays import write_annotated_preview_pdf
from geoworkbench.services.report_preview_marks import PreviewMark, PreviewMarkKind, PreviewOverlay
from geoworkbench.ui.interpretation_full_report_preview import FullReportPreviewDialog


def _source_pdf(path: Path) -> bytes:
    with fitz.open() as document:
        page = document.new_page(width=595, height=842)
        page.insert_text((70, 70), "Unchanged source geology")
        document.save(path)
    return path.read_bytes()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_page_click_text_undo_redo_pdf_save_preserves_original(
    qapp, tmp_path, monkeypatch, language,
):
    source = tmp_path / "source.pdf"
    raw = _source_pdf(source)

    def export(target: Path) -> None:
        target.write_bytes(source.read_bytes())

    dialog = FullReportPreviewDialog(
        source, language=language,
        refresh_document=lambda: None,
        edit_annotations=lambda: None,
        export_document=export,
    )
    try:
        dialog.mark_tool.setCurrentIndex(
            dialog.mark_tool.findData(PreviewMarkKind.TEXT),
        )
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("Текст отчёта", True))
        dialog.show()
        qapp.processEvents()
        page = dialog._page_labels[0]
        QTest.mouseClick(
            page, Qt.MouseButton.LeftButton,
            pos=QPoint(round(page.width() * 0.25), round(page.height() * 0.30)),
        )
        assert len(dialog._mark_history.current.marks) == 1
        assert dialog.mark_undo_button.isEnabled()
        dialog.mark_undo_button.click()
        assert not dialog._mark_history.current.marks
        assert dialog.mark_redo_button.isEnabled()
        dialog.mark_redo_button.click()
        assert dialog._mark_history.current.marks[0].text == "Текст отчёта"

        output = tmp_path / "annotated.pdf"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            lambda *args, **kwargs: (str(output), "PDF (*.pdf)"),
        )
        dialog.export_button.click()
        assert output.is_file()
        with fitz.open(output) as annotated:
            assert annotated.page_count == 1
            assert "Unchanged source geology" in annotated[0].get_text()
            assert annotated[0].get_images(full=True)
        assert source.read_bytes() == raw
    finally:
        dialog.close()
        qapp.processEvents()


def test_freehand_and_remove_preview_marks_with_history(qapp, tmp_path):
    source = tmp_path / "source.pdf"
    _source_pdf(source)
    dialog = FullReportPreviewDialog(
        source, refresh_document=lambda: None,
        edit_annotations=lambda: None,
        export_document=lambda path: None,
    )
    try:
        dialog.mark_tool.setCurrentIndex(dialog.mark_tool.findData(PreviewMarkKind.FREEHAND))
        dialog._page_pointer(0, 0.2, 0.3, phase="press")
        dialog._page_pointer(0, 0.3, 0.4, phase="move")
        dialog._page_pointer(0, 0.4, 0.5, phase="release")
        marks = dialog._mark_history.current.marks
        assert len(marks) == 1
        assert marks[0].kind is PreviewMarkKind.FREEHAND
        assert marks[0].points == ((0.2, 0.3), (0.3, 0.4), (0.4, 0.5))
        dialog.mark_tool.setCurrentIndex(dialog.mark_tool.findData("remove"))
        dialog._page_pointer(0, 0.2, 0.3, phase="press")
        assert not dialog._mark_history.current.marks
        dialog.mark_undo_button.click()
        assert dialog._mark_history.current.marks == marks
    finally:
        dialog.close()
        qapp.processEvents()


def test_overlay_export_is_atomic_and_refuses_missing_page(qapp, tmp_path):
    source = tmp_path / "source.pdf"
    unchanged = _source_pdf(source)
    existing = tmp_path / "existing.pdf"
    existing.write_bytes(b"old report")
    mark = PreviewMark(PreviewMarkKind.COMMENT, 1, 0.2, 0.3, text="Page two")
    with pytest.raises(ValueError, match="missing PDF page"):
        write_annotated_preview_pdf(source, existing, PreviewOverlay((mark,)))
    assert existing.read_bytes() == b"old report"
    with pytest.raises(ValueError, match="cannot be overwritten"):
        write_annotated_preview_pdf(
            source, source,
            PreviewOverlay((PreviewMark(PreviewMarkKind.TEXT, 0, 0.3, 0.4, text="x"),)),
        )
    assert source.read_bytes() == unchanged
    assert not list(tmp_path.glob(".geolog-preview-*"))
