"""Full-report proof keeps every PDF page inspectable across author edits."""

from pathlib import Path

import fitz
import pytest
from PySide6.QtWidgets import QFileDialog

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_full_report_preview import FullReportPreviewDialog


def _write_pdf(target: Path, page_count: int) -> None:
    with fitz.open() as document:
        for number in range(1, page_count + 1):
            page = document.new_page(width=595, height=842)
            page.insert_text((72, 72), f"Report page {number}", fontsize=12)
        document.save(target)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_all_pdf_pages_and_preview_regenerate_after_annotation_edit(
    qapp, tmp_path, monkeypatch, language,
):
    proof = tmp_path / "proof.pdf"
    _write_pdf(proof, 3)
    changes = []

    def edit_annotations() -> None:
        changes.append("edited")

    def regenerate() -> None:
        proof.unlink()
        _write_pdf(proof, 4 if changes else 3)

    def export(target: Path) -> None:
        target.write_bytes(proof.read_bytes())

    dialog = FullReportPreviewDialog(
        proof,
        language=language,
        refresh_document=regenerate,
        edit_annotations=edit_annotations,
        export_document=export,
    )
    try:
        assert dialog.page_count == 3
        assert len(dialog._page_labels) == 3
        assert dialog.edit_button.isEnabled()
        dialog.show()
        qapp.processEvents()
        assert dialog._page_labels[0].pixmap() is not None

        dialog.edit_button.click()
        qapp.processEvents()
        assert changes == ["edited"]
        assert dialog.page_count == 4
        assert [label.objectName() for label in dialog._page_labels] == [
            "full-report-page-1",
            "full-report-page-2",
            "full-report-page-3",
            "full-report-page-4",
        ]
        scrollbar = dialog.pages.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        qapp.processEvents()
        assert dialog._page_labels[-1].pixmap() is not None

        output = tmp_path / "export.pdf"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            lambda *args, **kwargs: (str(output), "PDF (*.pdf)"),
        )
        dialog.export_button.click()
        with fitz.open(output) as exported:
            assert exported.page_count == 4
        assert output.read_bytes() == proof.read_bytes()
    finally:
        dialog.close()
        qapp.processEvents()


def test_cancelled_annotation_dialog_regenerates_from_restored_state(qapp, tmp_path):
    proof = tmp_path / "proof.pdf"
    _write_pdf(proof, 2)
    refreshed = []
    dialog = FullReportPreviewDialog(
        proof,
        refresh_document=lambda: refreshed.append(True),
        edit_annotations=lambda: None,
        export_document=lambda destination: None,
    )
    try:
        dialog._edit_and_refresh()
        assert refreshed == [True]
        assert dialog.page_count == 2
    finally:
        dialog.close()
        qapp.processEvents()


def test_failed_visible_page_render_can_retry(qapp, tmp_path, monkeypatch):
    proof = tmp_path / "proof.pdf"
    _write_pdf(proof, 3)
    dialog = FullReportPreviewDialog(
        proof,
        refresh_document=lambda: None,
        edit_annotations=lambda: None,
        export_document=lambda destination: None,
    )
    errors = []
    original = fitz.Page.get_pixmap

    def fail_render(page, *args, **kwargs):
        raise RuntimeError("temporary render failure")

    monkeypatch.setattr(dialog, "_show_error", errors.append)
    monkeypatch.setattr(fitz.Page, "get_pixmap", fail_render)
    try:
        dialog.show()
        qapp.processEvents()
        assert errors
        assert not dialog._rendered_pages
        monkeypatch.setattr(fitz.Page, "get_pixmap", original)
        dialog._render_visible()
        assert 0 in dialog._rendered_pages
        assert not dialog._page_labels[0].pixmap().isNull()
    finally:
        dialog.close()
        qapp.processEvents()
