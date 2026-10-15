"""Scrollable complete-PDF proof with a bounded, native-page preview cache.

This view displays the *production* PDF, never a separately formatted HTML
surrogate. Author edits are made through the existing transactional editor;
the producer rebuilds the same PDF after Apply or Cancel.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import tempfile

import fitz
from PySide6.QtCore import QEvent, QObject, QRectF, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QImage, QMouseEvent, QPainter, QPixmap, QResizeEvent, QShowEvent
from PySide6.QtPrintSupport import QAbstractPrintDialog, QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
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
from geoworkbench.printing.report_preview_overlays import (
    paint_preview_marks,
    write_annotated_preview_pdf,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_preview_marks import (
    PreviewEditHistory,
    PreviewMark,
    PreviewMarkKind,
    PreviewOverlay,
    find_preview_mark,
    translate_preview_mark,
)


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
        add_gas_value_flag: Callable[[], None] | None = None,
        initial_marks: tuple[PreviewMark, ...] = (),
        on_marks_changed: Callable[[tuple[PreviewMark, ...]], None] | None = None,
        language: AppLanguage = AppLanguage.RU,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.pdf_path = Path(pdf_path)
        self._refresh_document = refresh_document
        self._edit_annotations = edit_annotations
        self._export_document = export_document
        self._add_gas_value_flag = add_gas_value_flag
        self._on_marks_changed = on_marks_changed
        self._language = language
        self._page_labels: list[QLabel] = []
        self._rendered_pages: set[int] = set()
        self._page_dimensions: list[tuple[float, float]] = []
        self._refresh_scheduled = False
        self._mark_history = PreviewEditHistory(current=PreviewOverlay(initial_marks))
        self._drawing_page: int | None = None
        self._stroke_points: list[tuple[float, float]] = []
        self._moving_mark: tuple[int, int, float, float, PreviewMark] | None = None
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
                "Выберите инструмент на странице PDF. «Переместить» — перетащите "
                "пометку, «Изменить текст» — щёлкните по ней. Изменения сохраняются в проекте.",
                "PDF бетінде құралды таңдаңыз. «Жылжыту» белгісін сүйрейді, "
                "«Мәтінді өзгерту» белгіге басқанда өңдейді. Өзгерістер жобада сақталады.",
                "Choose a tool on the PDF page. Drag a mark with Move, or click "
                "Edit text to revise it. Changes are saved in the project.",
            ),
            self,
        )
        self.help_label.setWordWrap(True)
        root.addWidget(self.help_label)

        tools = QHBoxLayout()
        tools.addWidget(QLabel(self._text("Инструмент", "Құрал", "Tool"), self))
        self.mark_tool = QComboBox(self)
        self.mark_tool.setObjectName("full-report-mark-tool")
        self.mark_tool.addItem(self._text("Просмотр", "Қарау", "View"), None)
        self.mark_tool.addItem(self._text("Текст", "Мәтін", "Text"), PreviewMarkKind.TEXT)
        self.mark_tool.addItem(
            self._text("Комментарий", "Пікір", "Comment"), PreviewMarkKind.COMMENT,
        )
        self.mark_tool.addItem(self._text("Символ", "Белгі", "Symbol"), PreviewMarkKind.SYMBOL)
        self.mark_tool.addItem(
            self._text("Карандаш", "Қарындаш", "Pencil"), PreviewMarkKind.FREEHAND,
        )
        self.mark_tool.addItem(self._text("Переместить", "Жылжыту", "Move"), "move")
        self.mark_tool.addItem(
            self._text("Изменить текст", "Мәтінді өзгерту", "Edit text"), "edit",
        )
        self.mark_tool.addItem(self._text("Удалить", "Жою", "Remove"), "remove")
        self.mark_tool.currentIndexChanged.connect(self._cancel_moving_mark)
        tools.addWidget(self.mark_tool)
        self.mark_undo_button = QPushButton(self._text("Отменить", "Болдырмау", "Undo"), self)
        self.mark_undo_button.setObjectName("full-report-mark-undo")
        self.mark_undo_button.clicked.connect(self._undo_mark)
        tools.addWidget(self.mark_undo_button)
        self.mark_redo_button = QPushButton(self._text("Повторить", "Қайталау", "Redo"), self)
        self.mark_redo_button.setObjectName("full-report-mark-redo")
        self.mark_redo_button.clicked.connect(self._redo_mark)
        tools.addWidget(self.mark_redo_button)
        tools.addStretch(1)
        root.addLayout(tools)
        self._sync_mark_buttons()

        actions = QHBoxLayout()
        self.edit_button = QPushButton(
            self._text("Аннотации…", "Аннотациялар…", "Annotations…"), self,
        )
        self.edit_button.setObjectName("full-report-edit-annotations")
        self.edit_button.clicked.connect(self._edit_and_refresh)
        actions.addWidget(self.edit_button)
        self.gas_flag_button = QPushButton(
            self._text("Газовый флажок…", "Газ жалаушасы…", "Gas value flag…"), self,
        )
        self.gas_flag_button.setObjectName("full-report-add-gas-value")
        self.gas_flag_button.setEnabled(add_gas_value_flag is not None)
        self.gas_flag_button.clicked.connect(self._add_gas_flag_and_refresh)
        actions.addWidget(self.gas_flag_button)
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
            label.installEventFilter(self)
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
        self._rendered_pages.intersection_update(requested)
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
                    preview = QPixmap.fromImage(image)
                    marks = tuple(
                        mark for mark in self._mark_history.current.marks
                        if mark.page == index
                    )
                    if marks:
                        painter = QPainter(preview)
                        try:
                            paint_preview_marks(
                                painter, QRectF(0, 0, preview.width(), preview.height()), marks,
                            )
                        finally:
                            painter.end()
                    label.setPixmap(preview)
                    # A failed render must remain eligible on the next view update.
                    self._rendered_pages.add(index)
        except (OSError, RuntimeError, ValueError) as exc:
            self._show_error(exc)

    def _sync_mark_buttons(self) -> None:
        self.mark_undo_button.setEnabled(bool(self._mark_history.undo_stack))
        self.mark_redo_button.setEnabled(bool(self._mark_history.redo_stack))

    def _update_marks(self, updated: PreviewEditHistory) -> None:
        if updated is self._mark_history:
            return
        if (
            updated.current != self._mark_history.current
            and self._on_marks_changed is not None
        ):
            try:
                # Persist first; reject stale-session edits without changing UI history.
                self._on_marks_changed(updated.current.marks)
            except (OSError, RuntimeError, ValueError) as exc:
                self._show_error(exc)
                return
        self._mark_history = updated
        self._sync_mark_buttons()
        self._rendered_pages.clear()
        self._schedule_visible_render()

    def _cancel_moving_mark(self) -> None:
        self._moving_mark = None

    def _undo_mark(self) -> None:
        self._update_marks(self._mark_history.undo())

    def _redo_mark(self) -> None:
        self._update_marks(self._mark_history.redo())

    def _page_pointer(self, page: int, x: float, y: float, *, phase: str) -> bool:
        """Apply the active page tool to normalized coordinates, never the source PDF."""
        tool_data = self.mark_tool.currentData()
        if tool_data is None:
            return False
        # Qt may return StrEnum data as its underlying string. Move, Edit
        # and Remove are editor commands, not PreviewMarkKind values.
        tool = tool_data
        if isinstance(tool_data, str) and tool_data not in {"move", "edit", "remove"}:
            try:
                tool = PreviewMarkKind(tool_data)
            except ValueError:
                return False
        if tool is PreviewMarkKind.FREEHAND:
            if phase == "press":
                self._drawing_page = page
                self._stroke_points = [(x, y)]
            elif phase == "move" and self._drawing_page == page:
                if len(self._stroke_points) < 4096:
                    self._stroke_points.append((x, y))
            elif phase == "release" and self._drawing_page == page:
                points = tuple(self._stroke_points + [(x, y)])
                self._drawing_page = None
                self._stroke_points = []
                if len(set(points)) >= 2 and len(points) <= 4096:
                    mark = PreviewMark(
                        PreviewMarkKind.FREEHAND, page, points[0][0], points[0][1],
                        points=points,
                    )
                    self._update_marks(
                        self._mark_history.apply(self._mark_history.current.add(mark)),
                    )
            return True
        if tool == "move":
            if phase == "press":
                index = find_preview_mark(self._mark_history.current.marks, page, x, y)
                self._moving_mark = None
                if index is not None:
                    self._moving_mark = (
                        page, index, x, y, self._mark_history.current.marks[index],
                    )
            elif phase == "release":
                grabbed = self._moving_mark
                self._moving_mark = None
                if grabbed is not None:
                    original_page, index, start_x, start_y, original = grabbed
                    current_marks = self._mark_history.current.marks
                    if (
                        page == original_page
                        and index < len(current_marks)
                        and current_marks[index] == original
                    ):
                        moved = translate_preview_mark(
                            original, x - start_x, y - start_y,
                        )
                        self._update_marks(self._mark_history.apply(
                            self._mark_history.current.replace(index, moved),
                        ))
            return True
        if phase != "press":
            return False
        if tool == "edit":
            index = find_preview_mark(self._mark_history.current.marks, page, x, y)
            if index is None:
                return True
            original = self._mark_history.current.marks[index]
            if original.kind is PreviewMarkKind.FREEHAND:
                return True
            title = self._text(
                "Изменить текст пометки", "Белгі мәтінін өзгерту", "Edit mark text",
            )
            value, accepted = QInputDialog.getMultiLineText(
                self, title, title, original.text,
            )
            if accepted:
                try:
                    edited = PreviewMark(
                        original.kind, original.page, original.x, original.y,
                        text=value, points=original.points,
                    )
                    self._update_marks(self._mark_history.apply(
                        self._mark_history.current.replace(index, edited),
                    ))
                except ValueError as exc:
                    self._show_error(exc)
            return True
        if tool == "remove":
            index = find_preview_mark(self._mark_history.current.marks, page, x, y)
            if index is not None:
                self._update_marks(self._mark_history.apply(
                    self._mark_history.current.remove(index),
                ))
            return True
        if not isinstance(tool, PreviewMarkKind):
            return False
        title = self._text("Текст на странице", "Беттегі мәтін", "Page mark text")
        value, accepted = QInputDialog.getText(self, title, title)
        if not accepted or not value.strip():
            return True
        try:
            mark = PreviewMark(tool, page, x, y, text=value)
            self._update_marks(
                self._mark_history.apply(self._mark_history.current.add(mark)),
            )
        except ValueError as exc:
            self._show_error(exc)
        return True

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if isinstance(watched, QLabel) and watched in self._page_labels and event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonRelease,
        ):
            mouse = event
            if isinstance(mouse, QMouseEvent) and (
                mouse.button() == Qt.MouseButton.LeftButton
                or mouse.buttons() & Qt.MouseButton.LeftButton
                or self._drawing_page is not None
            ):
                label = self._page_labels[self._page_labels.index(watched)]
                x = min(1.0, max(0.0, mouse.position().x() / max(1, label.width())))
                y = min(1.0, max(0.0, mouse.position().y() / max(1, label.height())))
                phase = {
                    QEvent.Type.MouseButtonPress: "press",
                    QEvent.Type.MouseMove: "move",
                    QEvent.Type.MouseButtonRelease: "release",
                }[event.type()]
                if self._page_pointer(self._page_labels.index(watched), x, y, phase=phase):
                    return True
        return super().eventFilter(watched, event)

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

    def _add_gas_flag_and_refresh(self) -> None:
        if self._add_gas_value_flag is None:
            return
        try:
            self._add_gas_value_flag()
        except (OSError, RuntimeError, ValueError) as exc:
            self._show_error(exc)
            return
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
            if self._mark_history.current.marks:
                with tempfile.TemporaryDirectory(prefix="geolog-preview-export-") as folder:
                    unmarked = Path(folder) / "report.pdf"
                    self._export_document(unmarked)
                    write_annotated_preview_pdf(
                        unmarked, target, self._mark_history.current,
                    )
            else:
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
            if self._mark_history.current.marks:
                with tempfile.TemporaryDirectory(prefix="geolog-preview-print-") as folder:
                    marked = Path(folder) / "annotated.pdf"
                    write_annotated_preview_pdf(
                        self.pdf_path, marked, self._mark_history.current,
                    )
                    print_pdf_page_selection(
                        marked, printer, selected, language=self._language,
                    )
            else:
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
