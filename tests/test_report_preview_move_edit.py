"""Full PDF preview moving and text editing via real Qt page events."""

from pathlib import Path

import fitz
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QInputDialog

from geoworkbench.services.report_preview_marks import (
    PreviewMark, PreviewMarkKind,
)
from geoworkbench.ui.interpretation_full_report_preview import FullReportPreviewDialog


def _pdf(path: Path) -> None:
    with fitz.open() as document:
        page = document.new_page(width=595, height=842)
        page.insert_text((65, 65), "Unchanged source data")
        document.new_page(width=595, height=842)
        document.save(path)


def _preview(path: Path, marks, callback):
    return FullReportPreviewDialog(
        path,
        initial_marks=marks,
        on_marks_changed=callback,
        refresh_document=lambda: None,
        edit_annotations=lambda: None,
        export_document=lambda target: target.write_bytes(path.read_bytes()),
    )


def _point(label, x, y):
    return QPoint(round(label.width() * x), round(label.height() * y))


def test_drag_existing_mark_undo_redo_and_export_with_real_qt_events(
    qapp, tmp_path, monkeypatch,
):
    source = tmp_path / "source.pdf"
    _pdf(source)
    before = source.read_bytes()
    initial = PreviewMark(PreviewMarkKind.COMMENT, 0, 0.2, 0.3, text="Скв. Максат")
    saved = []
    dialog = _preview(source, (initial,), saved.append)
    try:
        dialog.mark_tool.setCurrentIndex(dialog.mark_tool.findData("move"))
        dialog.show()
        qapp.processEvents()
        label = dialog._page_labels[0]
        QTest.mousePress(label, Qt.MouseButton.LeftButton, pos=_point(label, 0.2, 0.3))
        QTest.mouseRelease(label, Qt.MouseButton.LeftButton, pos=_point(label, 0.37, 0.51))
        assert len(saved) == 1
        moved = dialog._mark_history.current.marks[0]
        assert moved.page == 0 and moved.text == initial.text
        assert moved.x == pytest.approx(0.37, abs=0.003)
        assert moved.y == pytest.approx(0.51, abs=0.003)
        dialog.mark_undo_button.click()
        assert dialog._mark_history.current.marks == (initial,)
        dialog.mark_redo_button.click()
        assert dialog._mark_history.current.marks == (moved,)
        assert saved == [(moved,), (initial,), (moved,)]

        output = tmp_path / "moved-mark.pdf"
        monkeypatch.setattr(
            QFileDialog, "getSaveFileName",
            lambda *args, **kwargs: (str(output), "PDF (*.pdf)"),
        )
        dialog.export_button.click()
        with fitz.open(output) as exported:
            assert exported.page_count == 2
            assert exported[0].get_images(full=True)
            assert not exported[1].get_images(full=True)
        assert source.read_bytes() == before
    finally:
        dialog.close()
        qapp.processEvents()


def test_edit_existing_multiline_text_persists_and_cancel_is_noop(
    qapp, tmp_path, monkeypatch,
):
    source = tmp_path / "source.pdf"
    _pdf(source)
    initial = PreviewMark(PreviewMarkKind.TEXT, 1, 0.25, 0.4, text="Известняк")
    saved = []
    dialog = _preview(source, (initial,), saved.append)
    try:
        dialog.mark_tool.setCurrentIndex(dialog.mark_tool.findData("edit"))
        seen = []
        def edit_text(_parent, _title, _label, current):
            seen.append(current)
            return "Известняк\nТрещиноватый", True
        monkeypatch.setattr(QInputDialog, "getMultiLineText", edit_text)
        assert dialog._page_pointer(1, 0.25, 0.4, phase="press")
        changed = dialog._mark_history.current.marks[0]
        assert changed.text == "Известняк\nТрещиноватый"
        assert changed.x == initial.x and changed.y == initial.y
        assert seen == ["Известняк"]
        assert saved == [(changed,)]
        monkeypatch.setattr(
            QInputDialog, "getMultiLineText", lambda *args: ("Discarded", False),
        )
        dialog._page_pointer(1, 0.25, 0.4, phase="press")
        assert saved == [(changed,)]
        dialog.mark_undo_button.click()
        assert dialog._mark_history.current.marks == (initial,)
        dialog.mark_redo_button.click()
        assert dialog._mark_history.current.marks == (changed,)
    finally:
        dialog.close()
        qapp.processEvents()


def test_stroke_midpoint_drag_and_hit_target_removal(qapp, tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    stroke = PreviewMark(
        PreviewMarkKind.FREEHAND, 0, 0.1, 0.1,
        points=((0.1, 0.1), (0.5, 0.5)),
    )
    changes = []
    dialog = _preview(source, (stroke,), changes.append)
    try:
        dialog.mark_tool.setCurrentIndex(dialog.mark_tool.findData("move"))
        assert dialog._page_pointer(0, 0.3, 0.3, phase="press")
        assert dialog._page_pointer(0, 0.4, 0.4, phase="release")
        moved = dialog._mark_history.current.marks[0]
        assert moved.points[0][0] == pytest.approx(0.2)
        assert moved.points[-1][1] == pytest.approx(0.6)
        assert stroke.points[0][0] == 0.1
        dialog.mark_tool.setCurrentIndex(dialog.mark_tool.findData("remove"))
        assert dialog._page_pointer(0, 0.45, 0.45, phase="press")
        assert dialog._mark_history.current.marks == ()
        dialog.mark_undo_button.click()
        assert dialog._mark_history.current.marks == (moved,)
    finally:
        dialog.close()
        qapp.processEvents()


def test_rejected_save_does_not_change_preview_history_or_saved_marks(
    qapp, tmp_path,
):
    source = tmp_path / "source.pdf"
    _pdf(source)
    initial = PreviewMark(PreviewMarkKind.TEXT, 0, 0.15, 0.2, text="Original")
    attempts = []
    dialog = _preview(source, (initial,), lambda m: attempts.append(m))
    errors = []
    try:
        dialog.mark_tool.setCurrentIndex(dialog.mark_tool.findData("move"))
        dialog._on_marks_changed = lambda marks: (_ for _ in ()).throw(
            RuntimeError("stale well")
        )
        dialog._show_error = errors.append
        dialog._page_pointer(0, 0.15, 0.2, phase="press")
        dialog._page_pointer(0, 0.45, 0.55, phase="release")
        assert dialog._mark_history.current.marks == (initial,)
        assert not dialog._mark_history.undo_stack
        assert not attempts
        assert errors and "stale well" in str(errors[0])
        # Switching tools cancels an in-progress drag rather than applying it.
        dialog._on_marks_changed = attempts.append
        dialog._page_pointer(0, 0.15, 0.2, phase="press")
        dialog.mark_tool.setCurrentIndex(dialog.mark_tool.findData("remove"))
        dialog.mark_tool.setCurrentIndex(dialog.mark_tool.findData("move"))
        dialog._page_pointer(0, 0.5, 0.5, phase="release")
        assert dialog._mark_history.current.marks == (initial,)
        assert not attempts
    finally:
        dialog.close()
        qapp.processEvents()
