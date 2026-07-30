from __future__ import annotations

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from geoworkbench.ui.file_workspace_runtime import (
    FileWorkspaceWidget,
    runtime_catalogs_have_same_keys,
)


def _application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _dispose(widget: FileWorkspaceWidget) -> None:
    widget.close()
    widget.deleteLater()
    _application().processEvents()


def test_runtime_catalogs_have_identical_keys() -> None:
    assert runtime_catalogs_have_same_keys()


def test_open_document_dialog_uses_selected_language(monkeypatch) -> None:
    _application()
    calls: list[tuple[str, str]] = []

    def fake_open(parent, title, directory, file_filter):
        calls.append((title, file_filter))
        return "", ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_open)
    widget = FileWorkspaceWidget(language="en")
    widget._open_document()
    assert calls == [("Open document", "Documents (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp)")]
    _dispose(widget)


def test_common_pdf_error_is_localized_for_english_and_kazakh(monkeypatch) -> None:
    _application()
    calls: list[tuple[str, str]] = []

    def fake_warning(parent, title, message):
        calls.append((title, message))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)

    english = FileWorkspaceWidget(language="en")
    english._show_error("Сохранение", "Документ не открыт")
    kazakh = FileWorkspaceWidget(language="kk")
    kazakh._show_error("Сохранение", "Документ не открыт")

    assert calls[0] == ("Save", "No document is open")
    assert calls[1] == ("Сақтау", "Құжат ашылмаған")
    _dispose(english)
    _dispose(kazakh)
