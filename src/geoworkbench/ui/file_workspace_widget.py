from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from geoworkbench.files.archive_service import ArchiveError, ArchiveFormat, ArchiveService
from geoworkbench.files.datum import calculate_datum_elevations
from geoworkbench.files.document_service import DocumentError, DocumentKind, DocumentService
from geoworkbench.files.engineering import (
    EngineeringCalculator,
    EngineeringExpressionError,
    UnitConverter,
    format_engineering_value,
)
from geoworkbench.files.logo_service import LogoDesign, LogoDesignError, LogoService
from geoworkbench.files.pdf_tools import PdfTools, PdfToolsError


class _SelectionLabel(QLabel):
    selection_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setMouseTracking(True)
        self._start: QPoint | None = None
        self._selection = QRect()

    def selection(self) -> QRect:
        return QRect(self._selection)

    def clear_selection(self) -> None:
        self._start = None
        self._selection = QRect()
        self.selection_changed.emit(QRect())
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton and self.pixmap() is not None:
            self._start = event.position().toPoint()
            self._selection = QRect(self._start, self._start)
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if self._start is not None:
            point = event.position().toPoint()
            bounds = self.rect().adjusted(0, 0, -1, -1)
            point.setX(max(bounds.left(), min(bounds.right(), point.x())))
            point.setY(max(bounds.top(), min(bounds.bottom(), point.y())))
            self._selection = QRect(self._start, point).normalized()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton and self._start is not None:
            self.mouseMoveEvent(event)
            self._start = None
            self.selection_changed.emit(QRect(self._selection))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API
        super().paintEvent(event)
        if self._selection.isNull():
            return
        painter = QPainter(self)
        pen = QPen(QColor("#2563eb"))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.fillRect(self._selection, QColor(37, 99, 235, 38))
        painter.drawRect(self._selection)


class FileWorkspaceWidget(QWidget):
    """Independent document, archive and engineering workspace."""

    def __init__(self, parent: QWidget | None = None, *, language: str = "ru") -> None:
        super().__init__(parent)
        self.language = language
        self.document_service = DocumentService()
        self.archive_service = ArchiveService()
        self.calculator = EngineeringCalculator()
        self.converter = UnitConverter()
        self.logo_service = LogoService()
        self._render_zoom = 1.25
        self._archive_sources: list[Path] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        self.sections = QTabWidget(self)
        self.sections.setObjectName("fileWorkspaceSections")
        root.addWidget(self.sections)
        self.sections.addTab(self._build_document_tab(), "Документы")
        self.sections.addTab(self._build_pdf_tools_tab(), "PDF-инструменты")
        self.sections.addTab(self._build_logo_tab(), "Логотип")
        self.sections.addTab(self._build_archive_tab(), "Архивы")
        self.sections.addTab(self._build_engineering_tab(), "Инженерные расчёты")

    @staticmethod
    def tab_title(language: str) -> str:
        return {"ru": "Файлы", "kk": "Файлдар", "en": "Files"}.get(language, "Файлы")

    def _build_document_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._button("Открыть...", self._open_document))
        toolbar.addWidget(self._button("Сохранить", self._save_document))
        toolbar.addWidget(self._button("Сохранить как...", self._save_document_as))
        toolbar.addWidget(self._button("Отменить", self._undo_document))
        toolbar.addWidget(self._button("Повторить", self._redo_document))
        toolbar.addSpacing(12)
        toolbar.addWidget(self._button("◀", self._previous_page))
        self.page_label = QLabel("Страница —")
        toolbar.addWidget(self.page_label)
        toolbar.addWidget(self._button("▶", self._next_page))
        toolbar.addSpacing(12)
        toolbar.addWidget(QLabel("Масштаб:"))
        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(10, 800)
        self.zoom_spin.setValue(125)
        self.zoom_spin.setSuffix(" %")
        self.zoom_spin.valueChanged.connect(self._zoom_changed)
        toolbar.addWidget(self.zoom_spin)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        operations = QHBoxLayout()
        operations.addWidget(self._button("Текст PDF", self._add_pdf_text))
        operations.addWidget(self._button("Выделить PDF", self._highlight_pdf))
        operations.addWidget(self._button("Примечание PDF", self._note_pdf))
        operations.addWidget(self._button("Скрыть область PDF", self._redact_pdf))
        operations.addWidget(self._button("Удалить аннотации", self._delete_pdf_annotations))
        operations.addSpacing(12)
        operations.addWidget(self._button("Размер изображения", self._resize_image))
        operations.addWidget(self._button("Обрезать", self._crop_image))
        operations.addWidget(self._button("Коррекция", self._correct_image))
        operations.addStretch(1)
        layout.addLayout(operations)

        self.document_canvas = _SelectionLabel()
        self.document_canvas.setObjectName("fileDocumentCanvas")
        self.document_canvas.setText("Откройте PDF или изображение")
        self.document_canvas.setStyleSheet("QLabel { background: white; border: 1px solid #cbd5e1; }")
        self.document_scroll = QScrollArea()
        self.document_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.document_scroll.setWidget(self.document_canvas)
        self.document_scroll.setWidgetResizable(False)
        layout.addWidget(self.document_scroll, 1)

        self.document_status = QLabel("Поддерживаются PDF, JPEG, PNG, TIFF и BMP")
        self.document_status.setWordWrap(True)
        layout.addWidget(self.document_status)
        return page

    def _build_pdf_tools_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        explanation = QLabel(
            "Объединение сохраняет порядок выбранных файлов. Разделение создаёт отдельный PDF "
            "для каждой страницы. Экспорт DOCX переносит доступный текст без OCR."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        buttons = QHBoxLayout()
        buttons.addWidget(self._button("Объединить PDF...", self._merge_pdfs))
        buttons.addWidget(self._button("Разделить PDF...", self._split_pdf))
        buttons.addWidget(self._button("Экспорт PDF в DOCX...", self._export_pdf_docx))
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.pdf_tools_log = QTextEdit()
        self.pdf_tools_log.setReadOnly(True)
        self.pdf_tools_log.setPlaceholderText("Здесь появится результат операции")
        layout.addWidget(self.pdf_tools_log, 1)
        return page

    def _build_logo_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QHBoxLayout(page)
        controls = QWidget()
        form = QFormLayout(controls)
        self.logo_text = QTextEdit("BPServices")
        self.logo_text.setMaximumHeight(80)
        form.addRow("Текст:", self.logo_text)
        self.logo_width = self._integer_spin(16, 20_000, 1200)
        self.logo_height = self._integer_spin(16, 20_000, 360)
        self.logo_font_size = self._integer_spin(6, 2_000, 120)
        self.logo_foreground = QLineEdit("#0f172a")
        self.logo_background = QLineEdit("#ffffff")
        self.logo_transparent = QCheckBox("Прозрачный фон")
        self.logo_border_width = self._integer_spin(0, 200, 0)
        self.logo_border_color = QLineEdit("#0f172a")
        form.addRow("Ширина, px:", self.logo_width)
        form.addRow("Высота, px:", self.logo_height)
        form.addRow("Шрифт, px:", self.logo_font_size)
        form.addRow("Цвет текста:", self.logo_foreground)
        form.addRow("Цвет фона:", self.logo_background)
        form.addRow("", self.logo_transparent)
        form.addRow("Рамка, px:", self.logo_border_width)
        form.addRow("Цвет рамки:", self.logo_border_color)
        preview_button = self._button("Обновить предпросмотр", self._refresh_logo)
        save_button = self._button("Сохранить логотип...", self._save_logo)
        form.addRow(preview_button)
        form.addRow(save_button)
        layout.addWidget(controls)

        self.logo_preview = QLabel("Предпросмотр")
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_preview.setMinimumSize(480, 260)
        self.logo_preview.setStyleSheet("QLabel { background: #e2e8f0; border: 1px solid #94a3b8; }")
        layout.addWidget(self.logo_preview, 1)
        self._refresh_logo()
        return page

    def _build_archive_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        self.archive_capabilities = QLabel(self._archive_capability_text())
        self.archive_capabilities.setWordWrap(True)
        layout.addWidget(self.archive_capabilities)

        source_group = QGroupBox("Источники нового архива")
        source_layout = QVBoxLayout(source_group)
        source_buttons = QHBoxLayout()
        source_buttons.addWidget(self._button("Добавить файлы...", self._archive_add_files))
        source_buttons.addWidget(self._button("Добавить папку...", self._archive_add_folder))
        source_buttons.addWidget(self._button("Очистить", self._archive_clear_sources))
        source_buttons.addStretch(1)
        source_layout.addLayout(source_buttons)
        self.archive_source_list = QListWidget()
        source_layout.addWidget(self.archive_source_list)
        create_row = QHBoxLayout()
        self.archive_format_combo = QComboBox()
        for archive_format in ArchiveFormat:
            self.archive_format_combo.addItem(archive_format.value, archive_format)
        create_row.addWidget(QLabel("Формат:"))
        create_row.addWidget(self.archive_format_combo)
        create_row.addWidget(self._button("Создать архив...", self._archive_create))
        create_row.addStretch(1)
        source_layout.addLayout(create_row)
        layout.addWidget(source_group)

        operation_row = QHBoxLayout()
        operation_row.addWidget(self._button("Показать состав архива...", self._archive_inspect))
        operation_row.addWidget(self._button("Распаковать архив...", self._archive_extract))
        operation_row.addStretch(1)
        layout.addLayout(operation_row)
        self.archive_entries = QTreeWidget()
        self.archive_entries.setHeaderLabels(["Элемент", "Размер", "Тип"])
        layout.addWidget(self.archive_entries, 1)
        return page

    def _build_engineering_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        calculator_group = QGroupBox("Инженерный калькулятор")
        calculator_layout = QHBoxLayout(calculator_group)
        self.expression_input = QLineEdit("sqrt(144) + 2 1/2")
        self.expression_input.returnPressed.connect(self._calculate_expression)
        self.expression_result = QLineEdit()
        self.expression_result.setReadOnly(True)
        calculator_layout.addWidget(self.expression_input, 2)
        calculator_layout.addWidget(self._button("=", self._calculate_expression))
        calculator_layout.addWidget(self.expression_result, 1)
        layout.addWidget(calculator_group)

        converter_group = QGroupBox("Конвертер единиц")
        converter_layout = QGridLayout(converter_group)
        self.converter_category = QComboBox()
        for key, label in self.converter.categories():
            self.converter_category.addItem(label, key)
        self.converter_source = QComboBox()
        self.converter_target = QComboBox()
        self.converter_value = QLineEdit("1 1/2")
        self.converter_result = QLineEdit()
        self.converter_result.setReadOnly(True)
        self.converter_category.currentIndexChanged.connect(self._update_converter_units)
        converter_layout.addWidget(QLabel("Категория"), 0, 0)
        converter_layout.addWidget(QLabel("Значение"), 0, 1)
        converter_layout.addWidget(QLabel("Из"), 0, 2)
        converter_layout.addWidget(QLabel("В"), 0, 3)
        converter_layout.addWidget(QLabel("Результат"), 0, 5)
        converter_layout.addWidget(self.converter_category, 1, 0)
        converter_layout.addWidget(self.converter_value, 1, 1)
        converter_layout.addWidget(self.converter_source, 1, 2)
        converter_layout.addWidget(self.converter_target, 1, 3)
        converter_layout.addWidget(self._button("Преобразовать", self._convert_units), 1, 4)
        converter_layout.addWidget(self.converter_result, 1, 5)
        layout.addWidget(converter_group)
        self._update_converter_units()

        datum_group = QGroupBox("Вертикальные отметки скважины, м")
        datum_layout = QGridLayout(datum_group)
        labels = (
            "Абсолютная отметка datum",
            "GL относительно datum",
            "Wellhead над GL",
            "DF над GL",
            "RT над DF",
            "KB/RKB над RT",
        )
        self.datum_inputs: list[QDoubleSpinBox] = []
        defaults = (0.0, 0.0, 0.0, 6.0, 0.5, 0.3)
        for row, (label, default) in enumerate(zip(labels, defaults, strict=True)):
            spin = QDoubleSpinBox()
            spin.setRange(-1_000_000.0, 1_000_000.0)
            spin.setDecimals(4)
            spin.setValue(default)
            self.datum_inputs.append(spin)
            datum_layout.addWidget(QLabel(label), row, 0)
            datum_layout.addWidget(spin, row, 1)
        datum_layout.addWidget(self._button("Рассчитать отметки", self._calculate_datum), 6, 0, 1, 2)
        self.datum_table = QTableWidget(6, 2)
        self.datum_table.setHorizontalHeaderLabels(["Уровень", "Абсолютная отметка, м"])
        datum_layout.addWidget(self.datum_table, 0, 2, 7, 1)
        layout.addWidget(datum_group, 1)
        self._calculate_datum()
        return page

    @staticmethod
    def _button(text: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(callback)
        return button

    @staticmethod
    def _integer_spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def _show_error(self, title: str, error: Exception | str) -> None:
        QMessageBox.warning(self, title, str(error))

    def _open_document(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть документ",
            "",
            "Документы (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp)",
        )
        if not filename:
            return
        try:
            self.document_service.open(Path(filename))
            self._refresh_document()
        except DocumentError as exc:
            self._show_error("Открытие документа", exc)

    def _save_document(self) -> None:
        try:
            path = self.document_service.save()
            self.document_status.setText(f"Сохранено: {path}")
        except DocumentError as exc:
            self._show_error("Сохранение", exc)

    def _save_document_as(self) -> None:
        if not self.document_service.is_open:
            self._show_error("Сохранение", "Документ не открыт")
            return
        is_pdf = self.document_service.kind is DocumentKind.PDF
        file_filter = "PDF (*.pdf)" if is_pdf else "Изображения (*.png *.jpg *.tif *.bmp)"
        filename, _ = QFileDialog.getSaveFileName(self, "Сохранить документ как", "", file_filter)
        if not filename:
            return
        try:
            path = self.document_service.save_as(Path(filename))
            self.document_status.setText(f"Сохранено: {path}")
        except DocumentError as exc:
            self._show_error("Сохранение", exc)

    def _undo_document(self) -> None:
        self.document_service.undo()
        self._refresh_document()

    def _redo_document(self) -> None:
        self.document_service.redo()
        self._refresh_document()

    def _previous_page(self) -> None:
        if self.document_service.page_count:
            self.document_service.set_page(max(0, self.document_service.page_index - 1))
            self._refresh_document()

    def _next_page(self) -> None:
        if self.document_service.page_count:
            self.document_service.set_page(
                min(self.document_service.page_count - 1, self.document_service.page_index + 1)
            )
            self._refresh_document()

    def _zoom_changed(self, value: int) -> None:
        self._render_zoom = value / 100.0
        self._refresh_document()

    def _refresh_document(self) -> None:
        if not self.document_service.is_open:
            self.document_canvas.clear()
            self.document_canvas.setText("Откройте PDF или изображение")
            self.document_canvas.adjustSize()
            self.page_label.setText("Страница —")
            return
        try:
            rendered = self.document_service.render(self._render_zoom)
        except DocumentError as exc:
            self._show_error("Предпросмотр", exc)
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(rendered.payload, b"PNG"):
            self._show_error("Предпросмотр", "Не удалось декодировать изображение страницы")
            return
        self.document_canvas.setPixmap(pixmap)
        self.document_canvas.setFixedSize(pixmap.size())
        self.document_canvas.clear_selection()
        self.page_label.setText(f"Страница {rendered.page_index + 1} / {rendered.page_count}")
        path = self.document_service.path
        dirty = " • изменён" if self.document_service.dirty else ""
        self.document_status.setText(f"{path or 'Документ'}{dirty}")

    def _selected_document_rect(self) -> tuple[float, float, float, float]:
        selection = self.document_canvas.selection().normalized()
        if selection.width() < 2 or selection.height() < 2:
            raise DocumentError("Сначала выделите область мышью")
        scale = self._render_zoom
        return (
            selection.left() / scale,
            selection.top() / scale,
            (selection.right() + 1) / scale,
            (selection.bottom() + 1) / scale,
        )

    def _add_pdf_text(self) -> None:
        text, accepted = QInputDialog.getMultiLineText(self, "Текст PDF", "Текст:")
        if not accepted:
            return
        try:
            self.document_service.add_pdf_text(self._selected_document_rect(), text)
            self._refresh_document()
        except DocumentError as exc:
            self._show_error("Текст PDF", exc)

    def _highlight_pdf(self) -> None:
        try:
            self.document_service.add_pdf_highlight(self._selected_document_rect())
            self._refresh_document()
        except DocumentError as exc:
            self._show_error("Выделение PDF", exc)

    def _note_pdf(self) -> None:
        text, accepted = QInputDialog.getMultiLineText(self, "Примечание PDF", "Примечание:")
        if not accepted:
            return
        try:
            left, top, _right, _bottom = self._selected_document_rect()
            self.document_service.add_pdf_note((left, top), text)
            self._refresh_document()
        except DocumentError as exc:
            self._show_error("Примечание PDF", exc)

    def _redact_pdf(self) -> None:
        answer = QMessageBox.question(
            self,
            "Скрытие области PDF",
            "Удалить содержимое внутри выделенной области? Операцию можно отменить до сохранения.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.document_service.redact_pdf_area(self._selected_document_rect())
            self._refresh_document()
        except DocumentError as exc:
            self._show_error("Скрытие области PDF", exc)

    def _delete_pdf_annotations(self) -> None:
        try:
            count = self.document_service.delete_pdf_annotations(self._selected_document_rect())
            self._refresh_document()
            self.document_status.setText(f"Удалено аннотаций: {count}")
        except DocumentError as exc:
            self._show_error("Удаление аннотаций", exc)

    def _resize_image(self) -> None:
        size = self.document_service.image_size
        if size is None:
            self._show_error("Размер изображения", "Операция доступна только для изображения")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Размер изображения")
        form = QFormLayout(dialog)
        width = self._integer_spin(1, 100_000, size[0])
        height = self._integer_spin(1, 100_000, size[1])
        form.addRow("Ширина, px:", width)
        form.addRow("Высота, px:", height)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.document_service.resize_image(width.value(), height.value())
            self._refresh_document()
        except DocumentError as exc:
            self._show_error("Размер изображения", exc)

    def _crop_image(self) -> None:
        try:
            left, top, right, bottom = self._selected_document_rect()
            self.document_service.crop_image(
                (round(left), round(top), round(right), round(bottom))
            )
            self._refresh_document()
        except DocumentError as exc:
            self._show_error("Обрезка изображения", exc)

    def _correct_image(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Коррекция изображения")
        form = QFormLayout(dialog)
        controls: list[QDoubleSpinBox] = []
        for label in ("Яркость", "Контраст", "Насыщенность", "Резкость"):
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 4.0)
            spin.setSingleStep(0.1)
            spin.setValue(1.0)
            controls.append(spin)
            form.addRow(label, spin)
        grayscale = QCheckBox("Оттенки серого")
        autocontrast = QCheckBox("Автоконтраст")
        form.addRow(grayscale)
        form.addRow(autocontrast)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.document_service.correct_image(
                brightness=controls[0].value(),
                contrast=controls[1].value(),
                color=controls[2].value(),
                sharpness=controls[3].value(),
                grayscale=grayscale.isChecked(),
                autocontrast=autocontrast.isChecked(),
            )
            self._refresh_document()
        except DocumentError as exc:
            self._show_error("Коррекция изображения", exc)

    def _merge_pdfs(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Объединить PDF", "", "PDF (*.pdf)")
        if not files:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Результирующий PDF", "merged.pdf", "PDF (*.pdf)")
        if not target:
            return
        try:
            result = PdfTools.merge([Path(item) for item in files], Path(target))
            self.pdf_tools_log.append(f"Объединённый PDF: {result}")
        except PdfToolsError as exc:
            self._show_error("Объединение PDF", exc)

    def _split_pdf(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Разделить PDF", "", "PDF (*.pdf)")
        if not source:
            return
        destination = QFileDialog.getExistingDirectory(self, "Папка для страниц")
        if not destination:
            return
        try:
            results = PdfTools.split(Path(source), Path(destination))
            self.pdf_tools_log.append(f"Создано страниц: {len(results)}\n{destination}")
        except PdfToolsError as exc:
            self._show_error("Разделение PDF", exc)

    def _export_pdf_docx(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "PDF для экспорта", "", "PDF (*.pdf)")
        if not source:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Сохранить DOCX", "document.docx", "DOCX (*.docx)")
        if not target:
            return
        try:
            result = PdfTools.export_text_docx(Path(source), Path(target))
            self.pdf_tools_log.append(f"DOCX: {result}")
        except PdfToolsError as exc:
            self._show_error("Экспорт PDF в DOCX", exc)

    def _logo_design(self) -> LogoDesign:
        return LogoDesign(
            text=self.logo_text.toPlainText(),
            width=self.logo_width.value(),
            height=self.logo_height.value(),
            font_size=self.logo_font_size.value(),
            foreground=self.logo_foreground.text(),
            background=self.logo_background.text(),
            transparent_background=self.logo_transparent.isChecked(),
            border_width=self.logo_border_width.value(),
            border_color=self.logo_border_color.text(),
        )

    def _refresh_logo(self) -> None:
        try:
            image = self.logo_service.render(self._logo_design())
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            pixmap = QPixmap()
            if not pixmap.loadFromData(buffer.getvalue(), b"PNG"):
                raise LogoDesignError("Не удалось создать предпросмотр")
            preview = pixmap.scaled(
                self.logo_preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_preview.setPixmap(preview)
        except LogoDesignError as exc:
            self._show_error("Конструктор логотипов", exc)

    def _save_logo(self) -> None:
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить логотип",
            "logo.png",
            "Изображения (*.png *.jpg *.bmp *.tif)",
        )
        if not target:
            return
        try:
            result = self.logo_service.save(self._logo_design(), Path(target))
            self.logo_preview.setToolTip(str(result))
        except LogoDesignError as exc:
            self._show_error("Сохранение логотипа", exc)

    def _archive_capability_text(self) -> str:
        parts = []
        for capability in self.archive_service.capabilities():
            create = "создание" if capability.can_create else "без создания"
            extract = "распаковка" if capability.can_extract else "без распаковки"
            details = f" — {capability.explanation}" if capability.explanation else ""
            parts.append(f"{capability.archive_format.value}: {create}, {extract}{details}")
        return "\n".join(parts)

    def _archive_add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Добавить файлы в архив")
        for filename in files:
            self._add_archive_source(Path(filename))

    def _archive_add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Добавить папку в архив")
        if folder:
            self._add_archive_source(Path(folder))

    def _add_archive_source(self, path: Path) -> None:
        resolved = path.resolve()
        if resolved not in self._archive_sources:
            self._archive_sources.append(resolved)
            self.archive_source_list.addItem(str(resolved))

    def _archive_clear_sources(self) -> None:
        self._archive_sources.clear()
        self.archive_source_list.clear()

    def _archive_create(self) -> None:
        archive_format = self.archive_format_combo.currentData()
        if not isinstance(archive_format, ArchiveFormat):
            self._show_error("Создание архива", "Не выбран формат архива")
            return
        suffix = f".{archive_format.value}"
        target, _ = QFileDialog.getSaveFileName(self, "Создать архив", f"archive{suffix}")
        if not target:
            return
        try:
            result = self.archive_service.create(
                Path(target), tuple(self._archive_sources), archive_format
            )
            QMessageBox.information(self, "Архив", f"Создано: {result}")
        except ArchiveError as exc:
            self._show_error("Создание архива", exc)

    def _archive_inspect(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть архив",
            "",
            "Архивы (*.zip *.7z *.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz *.rar)",
        )
        if not source:
            return
        try:
            entries = self.archive_service.list_entries(Path(source))
            self.archive_entries.clear()
            for entry in entries:
                QTreeWidgetItem(
                    self.archive_entries,
                    [entry.name, str(entry.size), "папка" if entry.is_directory else "файл"],
                )
        except ArchiveError as exc:
            self._show_error("Состав архива", exc)

    def _archive_extract(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            "Распаковать архив",
            "",
            "Архивы (*.zip *.7z *.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz *.rar)",
        )
        if not source:
            return
        destination = QFileDialog.getExistingDirectory(self, "Папка распаковки")
        if not destination:
            return
        try:
            results = self.archive_service.extract(Path(source), Path(destination))
            QMessageBox.information(self, "Архив", f"Извлечено объектов: {len(results)}")
        except ArchiveError as exc:
            self._show_error("Распаковка архива", exc)

    def _calculate_expression(self) -> None:
        try:
            result = self.calculator.evaluate(self.expression_input.text())
            self.expression_result.setText(format_engineering_value(result))
        except EngineeringExpressionError as exc:
            self._show_error("Калькулятор", exc)

    def _update_converter_units(self) -> None:
        category = self.converter_category.currentData()
        if not isinstance(category, str):
            return
        units = self.converter.units(category)
        self.converter_source.clear()
        self.converter_target.clear()
        for key, label in units:
            self.converter_source.addItem(label, key)
            self.converter_target.addItem(label, key)
        if self.converter_target.count() > 1:
            self.converter_target.setCurrentIndex(1)

    def _convert_units(self) -> None:
        category = self.converter_category.currentData()
        source = self.converter_source.currentData()
        target = self.converter_target.currentData()
        if not all(isinstance(item, str) for item in (category, source, target)):
            return
        try:
            result = self.converter.convert(self.converter_value.text(), category, source, target)
            self.converter_result.setText(format_engineering_value(result))
        except (EngineeringExpressionError, KeyError, ValueError) as exc:
            self._show_error("Конвертер", exc)

    def _calculate_datum(self) -> None:
        values = [control.value() for control in self.datum_inputs]
        try:
            result = calculate_datum_elevations(
                datum_elevation_m=values[0],
                gl_offset_m=values[1],
                wellhead_above_gl_m=values[2],
                df_above_gl_m=values[3],
                rt_above_df_m=values[4],
                kb_above_rt_m=values[5],
            )
        except ValueError as exc:
            self._show_error("Вертикальные отметки", exc)
            return
        for row, (name, value) in enumerate(result.as_rows()):
            self.datum_table.setItem(row, 0, QTableWidgetItem(name))
            self.datum_table.setItem(row, 1, QTableWidgetItem(format_engineering_value(value)))
