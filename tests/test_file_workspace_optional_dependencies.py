from __future__ import annotations

import builtins
import sys

from PySide6.QtWidgets import QApplication, QLabel

from geoworkbench.ui.file_workspace_widget import (
    FileWorkspaceWidget,
    _is_optional_dependency_error,
)


def _application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_optional_dependency_classifier_accepts_pdf_and_image_modules() -> None:
    for name in ("pymupdf", "fitz", "PIL", "PIL.Image"):
        error = ModuleNotFoundError(f"No module named {name!r}", name=name)
        assert _is_optional_dependency_error(error)

    unrelated = ModuleNotFoundError("No module named 'unexpected'", name="unexpected")
    assert not _is_optional_dependency_error(unrelated)


def test_files_workspace_falls_back_without_pdf_dependency(monkeypatch) -> None:
    _application()
    monkeypatch.delitem(
        sys.modules,
        "geoworkbench.ui.file_workspace_full_widget",
        raising=False,
    )
    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "geoworkbench.ui.file_workspace_full_widget":
            raise ModuleNotFoundError("No module named 'fitz'", name="fitz")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    widget = FileWorkspaceWidget(language="ru")

    assert widget.objectName() == "fileWorkspaceDependencyFallback"
    assert FileWorkspaceWidget.tab_title("ru") == "Файлы / PDF / Калькулятор"
    labels = [label.text() for label in widget.findChildren(QLabel)]
    assert any("Основное приложение продолжает работать" in text for text in labels)
    assert any("PyMuPDF" in text and "Pillow" in text for text in labels)
    widget.deleteLater()
