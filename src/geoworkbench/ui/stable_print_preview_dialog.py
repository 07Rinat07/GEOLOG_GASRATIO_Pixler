from __future__ import annotations

from PySide6.QtPrintSupport import QPrinter, QPrintPreviewWidget
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QWidget


class StablePrintPreviewDialog(QDialog):
    """Application-owned print preview without QPrintPreviewDialog.

    QPrintPreviewDialog enters a native Windows preview/dialog path that has
    produced unrecoverable access violations on some printer-driver stacks.
    QPrintPreviewWidget keeps preview painting inside our ordinary QDialog and
    leaves printer selection/execution to the existing Print Center.
    """

    def __init__(
        self,
        printer: QPrinter,
        parent: QWidget | None = None,
        *,
        title: str = "",
    ) -> None:
        super().__init__(parent)
        if title:
            self.setWindowTitle(title)
        self.setObjectName("stable-print-preview-dialog")
        self.preview_widget = QPrintPreviewWidget(printer, self)
        self.preview_widget.setObjectName("stable-print-preview-widget")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.clicked.connect(self.reject)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.preview_widget, 1)
        layout.addWidget(buttons)
        self.resize(1000, 720)


__all__ = ["StablePrintPreviewDialog"]
