"""Scrollable complete-PDF proof with a bounded, native-page preview cache.

This view displays the *production* PDF, never a separately formatted HTML
surrogate. Author edits are made through the existing transactional editor;
the producer rebuilds the same PDF after Apply or Cancel.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import fitz
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QImage, QPixmap, QResizeEvent, QShowEvent
from PySide6.QtPrintSupport import QAbstractPrintDialog, QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.printing.hydrocarbon_interpretation_system_print import (
    configure_interpretation_printer,
    print_pdf_page_selection,
    selected_report_pages,
)
from geoworkbench.services.localization import AppLanguage


class FullReportPreviewDialog(QDialog):
    """All-page report proof with lazy rendering and transactional authoring."""

    _BASE_PAGE_WIDTH = 760
    _PREFETCH_PIXELS = 450

    def __init__(
        self,
        pdf_path: Path,
        *,
        refresh_document: Callable[[], None],
        edit_annotations: Callable[[], None],
        export_document: Callable[[Path], None],
        language: AppLanguage = AppLanguage.RU,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.pdf_path = Path(pdf_path)
        self._refresh_document = refresh_document
        self._edit_annotations = edit_annotations
        self._export_document = export_document
        self._language = language
        self._page_labels: list[QLabel] = []
        self._rendered_pages: set[int] = set()
        self._page_dimensions: list[tuple[float, float]] = []
        self._refresh_scheduled = False
        self.setObjectName("full-report-preview-dialog")
        self.setWindowTitle(self._text("Полный предпросмотр отчёта", "Есепті толық қарау", "Full report preview"))
        self.resize(1070, 830)

        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.page_count_label = QLabel(self)
        self.page_count_label.setObjectName("full-report-page-count")
        toolbar.addWidget(self.page_count_label)
        toolbar.addStretch(1)

        toolbar.addWidget(QLabel(self._text("Масштаб", "Масштаб", "Zoom"), self))
        self.zoom = QComboBox(self)
        self.zoom.setObjectName("full-report-zoom")
        for factor, name in ((0.75, "75%"), (1.0, "100%"), (1.25, "125%")):
            self.zoom.addItem(name, factor)
        self.zoom.setCurrentIndex(1)
        self.zoom.currentIndexChanged.connect(self._apply_zoom)
        toolbar.addWidget(self.zoom)
        root.addLayout(toolbar)

        self.pages = QScrollArea(self)
        self.pages.setObjectName("full-report-scroll")
        self.pages.setWidgetResizable(True)
        self.pages.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.pages.setStyleSheet("QScrollArea { background-color: #e7e9ee; }")
        self.container = QWidget(self.pages)
        self.page_layout = QVBoxLayout(self.container)
        self.page_layout.setContentsMargins(20, 20, 20, 20)
        self.page_layout.setSpacing(26)
        self.pages.setWidget(self.container)
        self.pages.verticalScrollBar().valueChanged.connect(self._schedule_visible_render)
        root.addWidget(self.pages, 1)

        self.help_label = QLabel(
            self._text(
                "Все страницы PDF. Для добавления текста, символов или комментариев "
                "используйте «Аннотации», затем проверьте обновлённый документ.",
                "PDF-тің барлық беттері. Мәтін, белгілер және пікірлер үшін "
                "«Аннотациялар» батырмасын қолданып, нәтижені қайта тексеріңіз.",
                "All PDF pages. Use Annotations to add text, symbols and comments, "
                "then verify the regenerated document.",
            ),
            self,
        )
        self.help_label.setWordWrap(True)
        root.addWidget(self.help_label)

        actions = QHBoxLayout()
        self.edit_button = QPushButton(
            self._text("Аннотации…", "Аннотациялар…", "Annotations…"), self,
        )
        self.edit_button.setObjectName("full-report-edit-annotations")
        self.edit_button.clicked.connect(self._edit_and_refresh)
        actions.addWidget(self.edit_button)
        self.refresh_button = QPushButton(self._text("Обновить", "Жаңарту", "Refresh"), self)
        self.refresh_button.setObjectName("full-report-refresh")
        self.refresh_button.clicked.connect(self._rebuild)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        self.export_button = QPushButton(self._text("Сохранить PDF…", "PDF сақтау…", "Save PDF…"), self)
        self.export_button.setObjectName("full-report-save-pdf")
        self.export_button.clicked.connect(self._save_pdf)
        actions.addWidget(self.export_button)
        self.print_button = QPushButton(self._text("Печать…", "Басып шығару…", "Print…"), self)
        self.print_button.setObjectName("full-report-print")
        self.print_button.clicked.connect(self._print_pdf)
        actions.addWidget(self.print_button)
        self.close_button = QPushButton(self._text("Закрыть", "Жабу", "Close"), self)
        self.close_button.clicked.connect(self.accept)
        actions.addWidget(self.close_button)
        root.addLayout(actions)
        self._load_page_geometry()

    def _text(self, ru: str, kk: str, en: str) -> str:
        return {AppLanguage.RU: ru, AppLanguage.KK: kk, AppLanguage.EN: en}[self._language]

    @property
    def page_count(self) -> int:
        return len(self._page_dimensions)

    def _load_page_geometry(self) -> None:
        with fitz.open(self.pdf_path) as source:
            dimensions = [(float(page.rect.width), float(page.rect.height)) for page in source]
        if not dimensions or any(width <= 0 or height <= 0 for width, height in dimensions):
            raise ValueError("The report PDF contains no valid pages")
        for label in self._page_labels:
            self.page_layout.removeWidget(label)
            label.deleteLater()
        self._page_labels.clear()
        self._rendered_pages.clear()
        self._page_dimensions = dimensions
        self.page_count_label.setText(
            self._text(
                f"Страниц: {len(dimensions)}",
                f"Беттер: {len(dimensions)}",
                f"Pages: {len(dimensions)}",
            )
        )
        for number in range(len(dimensions)):
            label = QLabel(self.container)
            label.setObjectName(f"full-report-page-{number + 1}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("QLabel { background: white; border: 1px solid #b8c0cb; }")
            label.setText(f"{number + 1} / {len(dimensions)}")
            self.page_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._page_labels.append(label)
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        factor = float(self.zoom.currentData() or 1.0)
        for label, (width, height) in zip(self._page_labels, self._page_dimensions, strict=True):
            page_width = round(self._BASE_PAGE_WIDTH * factor)
            page_height = round(page_width * height / width)
            label.setFixedSize(page_width, page_height)
            label.clear()
        self._rendered_pages.clear()
        self._schedule_visible_render()

    def _schedule_visible_render(self) -> None:
        if self._refresh_scheduled:
            return
        self._refresh_scheduled = True
        QTimer.singleShot(0, self._render_visible)

    def _render_visible(self) -> None:
        self._refresh_scheduled = False
        if not self.isVisible() or not self._page_labels:
            return
        scroll = self.pages.verticalScrollBar()
        top = scroll.value() - self._PREFETCH_PIXELS
        bottom = scroll.value() + self.pages.viewport().height() + self._PREFETCH_PIXELS
        requested: set[int] = set()
        for index, label in enumerate(self._page_labels):
            if label.y() + label.height() >= top and label.y() <= bottom:
                requested.add(index)
        for index in self._rendered_pages - requested:
            self._page_labels[index].clear()
        required = requested - self._rendered_pages
        self._rendered_pages = requested
        if not required:
            return
        try:
            with fitz.open(self.pdf_path) as source:
                for index in sorted(required):
                    label = self._page_labels[index]
                    page = source[index]
                    zoom = label.width() / float(page.rect.width)
                    pixmap = page.get_pixmap(
                        matrix=fitz.Matrix(zoom, zoom),
                        colorspace=fitz.csRGB,
                        alpha=False,
                    )
                    # QImage must own the copy before MuPDF frees the buffer.
                    image = QImage(
                        pixmap.samples,
                        pixmap.width,
                        pixmap.height,
                        pixmap.stride,
                        QImage.Format.Format_RGB888,
                    ).copy()
                    label.setPixmap(QPixmap.fromImage(image))
        except (OSError, RuntimeError, ValueError) as exc:
            self._show_error(exc)

    def _rebuild(self) -> None:
        fraction = self.pages.verticalScrollBar().value() / max(
            1, self.pages.verticalScrollBar().maximum(),
        )
        try:
            self._refresh_document()
            self._load_page_geometry()
        except (OSError, RuntimeError, ValueError) as exc:
            self._show_error(exc)
            return
        self.pages.verticalScrollBar().setValue(
            round(self.pages.verticalScrollBar().maximum() * fraction),
        )
        self._schedule_visible_render()

    def _edit_and_refresh(self) -> None:
        try:
            self._edit_annotations()
        except (OSError, RuntimeError, ValueError) as exc:
            self._show_error(exc)
            return
        # Also refresh after Cancel: the editor restores its checkpoint.
        self._rebuild()

    def _save_pdf(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._text("Сохранить отчёт PDF", "PDF есебін сақтау", "Save report PDF"),
            "",
            "PDF (*.pdf)",
        )
        if not filename:
            return
        target = Path(filename)
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
        if target.exists():
            confirm = QMessageBox.question(
                self,
                self.windowTitle(),
                self._text("Заменить существующий PDF?", "Бар PDF-ті ауыстыру керек пе?", "Replace existing PDF?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        try:
            self._export_document(target)
        except (OSError, RuntimeError, ValueError) as exc:
            self._show_error(exc)
            return

    def _print_pdf(self) -> None:
        if not self.page_count:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        first_width, first_height = self._page_dimensions[0]
        from PySide6.QtGui import QPageLayout
        orientation = (
            QPageLayout.Orientation.Landscape
            if first_width > first_height else QPageLayout.Orientation.Portrait
        )
        configure_interpretation_printer(printer, orientation)
        dialog = QPrintDialog(printer, self)
        dialog.setOption(QAbstractPrintDialog.PrintDialogOption.PrintPageRange, True)
        dialog.setMinMax(1, self.page_count)
        dialog.setFromTo(1, self.page_count)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = selected_report_pages(
            self.page_count,
            dialog.printRange(),
            dialog.fromPage() or printer.fromPage(),
            dialog.toPage() or printer.toPage(),
        )
        try:
            # Printer drivers may override the chosen paper; restore preview geometry.
            configure_interpretation_printer(printer, orientation)
            print_pdf_page_selection(
                self.pdf_path, printer, selected, language=self._language,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            self._show_error(exc)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._schedule_visible_render()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._schedule_visible_render()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._rendered_pages.clear()
        super().closeEvent(event)

    def _show_error(self, exc: Exception) -> None:
        QMessageBox.warning(self, self.windowTitle(), str(exc))
