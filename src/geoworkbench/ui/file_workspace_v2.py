from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.files.document_service import DocumentError, DocumentKind
from geoworkbench.files.enhanced_document_service import EnhancedDocumentService
from geoworkbench.files.petroleum_calculations import (
    annular_volume,
    circulation_time_minutes,
    equivalent_circulating_density,
    formation_elevations,
    hydrostatic_pressure,
    mixed_fluid_density,
    pipe_geometry,
)
from geoworkbench.ui.file_workspace_expert import (
    FileWorkspaceWidget as _ExpertFileWorkspaceWidget,
)
from geoworkbench.ui.file_workspace_i18n import normalize_language, text


class _EraserOverlay(QWidget):
    stroke_completed = Signal(object, int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self._active = False
        self._drawing = False
        self._brush_size = 36
        self._cursor = QPoint(-10_000, -10_000)
        self._points: list[QPointF] = []
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._drawing = False
        self._points.clear()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not active)
        self.setCursor(Qt.CursorShape.BlankCursor if active else Qt.CursorShape.ArrowCursor)
        self.update()

    def set_brush_size(self, size: int) -> None:
        self._brush_size = max(8, min(180, size))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._active and event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._points = [event.position()]
            self._cursor = event.position().toPoint()
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._active:
            super().mouseMoveEvent(event)
            return
        self._cursor = event.position().toPoint()
        if self._drawing:
            point = event.position()
            if not self._points or self._distance(self._points[-1], point) >= max(
                2.0, self._brush_size / 5.0
            ):
                self._points.append(point)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._active and event.button() == Qt.MouseButton.LeftButton and self._drawing:
            point = event.position()
            if not self._points or self._distance(self._points[-1], point) > 0.5:
                self._points.append(point)
            self._drawing = False
            points = list(self._points)
            self._points.clear()
            self.update()
            if points:
                self.stroke_completed.emit(points, self._brush_size)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        if not self._drawing:
            self._cursor = QPoint(-10_000, -10_000)
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self._active:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        half = self._brush_size / 2.0
        fill = QColor(255, 255, 255, 190)
        outline = QPen(QColor(220, 38, 38, 230))
        outline.setWidth(2)
        painter.setPen(outline)
        painter.setBrush(fill)
        for point in self._points:
            painter.drawRect(
                round(point.x() - half),
                round(point.y() - half),
                self._brush_size,
                self._brush_size,
            )
        painter.drawRect(
            round(self._cursor.x() - half),
            round(self._cursor.y() - half),
            self._brush_size,
            self._brush_size,
        )

    @staticmethod
    def _distance(left: QPointF, right: QPointF) -> float:
        return math.hypot(right.x() - left.x(), right.y() - left.y())


@dataclass(frozen=True, slots=True)
class _TextStyle:
    text: str
    fontname: str
    font_size: float
    color: tuple[float, float, float]
    alignment: int
    background: tuple[float, float, float] | None


class _PdfTextDialog(QDialog):
    def __init__(self, language: str, *, replace: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language = normalize_language(language)
        self.setWindowTitle(
            text(self.language, "replace_dialog_title" if replace else "text_dialog_title")
        )
        self.resize(620, 520)
        self._text_color = QColor("#000000")
        self._background_color = QColor("#ffffff")

        root = QVBoxLayout(self)
        instruction = QLabel(text(self.language, "text_instruction"), self)
        instruction.setWordWrap(True)
        root.addWidget(instruction)

        form = QFormLayout()
        self.editor = QTextEdit(self)
        self.editor.setMinimumHeight(150)
        form.addRow(text(self.language, "text_label"), self.editor)

        self.family = QComboBox(self)
        self.family.addItem(text(self.language, "font_helvetica"), "helv")
        self.family.addItem(text(self.language, "font_times"), "tiro")
        self.family.addItem(text(self.language, "font_courier"), "cour")
        form.addRow(text(self.language, "font_family"), self.family)

        self.size = QDoubleSpinBox(self)
        self.size.setRange(4.0, 144.0)
        self.size.setDecimals(1)
        self.size.setValue(11.0)
        self.size.setSuffix(" pt")
        self.size.setMinimumWidth(150)
        form.addRow(text(self.language, "font_size"), self.size)

        style_row = QHBoxLayout()
        self.bold = QCheckBox(text(self.language, "bold"), self)
        self.italic = QCheckBox(text(self.language, "italic"), self)
        style_row.addWidget(self.bold)
        style_row.addWidget(self.italic)
        style_row.addStretch(1)
        form.addRow(style_row)

        self.text_color_button = QPushButton(text(self.language, "text_color"), self)
        self.text_color_button.clicked.connect(self._choose_text_color)
        form.addRow(self.text_color_button)

        self.background_enabled = QCheckBox(text(self.language, "background_enabled"), self)
        self.background_button = QPushButton(text(self.language, "background_color"), self)
        self.background_button.setEnabled(False)
        self.background_enabled.toggled.connect(self.background_button.setEnabled)
        self.background_button.clicked.connect(self._choose_background_color)
        background_row = QHBoxLayout()
        background_row.addWidget(self.background_enabled)
        background_row.addWidget(self.background_button)
        background_row.addStretch(1)
        form.addRow(background_row)

        self.alignment = QComboBox(self)
        self.alignment.addItem(text(self.language, "align_left"), 0)
        self.alignment.addItem(text(self.language, "align_center"), 1)
        self.alignment.addItem(text(self.language, "align_right"), 2)
        form.addRow(text(self.language, "alignment"), self.alignment)
        root.addLayout(form)

        preview_title = QLabel(text(self.language, "preview"), self)
        preview_title.setStyleSheet("font-weight: 700;")
        root.addWidget(preview_title)
        self.preview = QLabel(self)
        self.preview.setMinimumHeight(90)
        self.preview.setWordWrap(True)
        self.preview.setFrameShape(QFrame.Shape.StyledPanel)
        root.addWidget(self.preview)

        self.editor.textChanged.connect(self._update_preview)
        self.family.currentIndexChanged.connect(self._update_preview)
        self.size.valueChanged.connect(self._update_preview)
        self.bold.toggled.connect(self._update_preview)
        self.italic.toggled.connect(self._update_preview)
        self.background_enabled.toggled.connect(self._update_preview)
        self.alignment.currentIndexChanged.connect(self._update_preview)

        buttons = QDialogButtonBox(self)
        apply_button = buttons.addButton(
            text(self.language, "apply"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        cancel_button = buttons.addButton(
            text(self.language, "cancel"), QDialogButtonBox.ButtonRole.RejectRole
        )
        apply_button.clicked.connect(self._accept_checked)
        cancel_button.clicked.connect(self.reject)
        root.addWidget(buttons)
        self._update_color_buttons()
        self._update_preview()

    def style(self) -> _TextStyle:
        base = str(self.family.currentData())
        fontname = self._font_variant(base, self.bold.isChecked(), self.italic.isChecked())
        background = (
            self._rgb(self._background_color) if self.background_enabled.isChecked() else None
        )
        return _TextStyle(
            text=self.editor.toPlainText(),
            fontname=fontname,
            font_size=self.size.value(),
            color=self._rgb(self._text_color),
            alignment=int(self.alignment.currentData()),
            background=background,
        )

    def _accept_checked(self) -> None:
        if not self.editor.toPlainText().strip():
            QMessageBox.warning(self, self.windowTitle(), text(self.language, "text_empty"))
            return
        self.accept()

    def _choose_text_color(self) -> None:
        color = QColorDialog.getColor(
            self._text_color, self, text(self.language, "color_dialog")
        )
        if color.isValid():
            self._text_color = color
            self._update_color_buttons()
            self._update_preview()

    def _choose_background_color(self) -> None:
        color = QColorDialog.getColor(
            self._background_color, self, text(self.language, "color_dialog")
        )
        if color.isValid():
            self._background_color = color
            self._update_color_buttons()
            self._update_preview()

    def _update_color_buttons(self) -> None:
        self.text_color_button.setStyleSheet(
            f"background:{self._text_color.name()}; color:{self._contrast(self._text_color)};"
        )
        self.background_button.setStyleSheet(
            f"background:{self._background_color.name()}; "
            f"color:{self._contrast(self._background_color)};"
        )

    def _update_preview(self, *_args: object) -> None:
        family = {
            "helv": "Arial",
            "tiro": "Times New Roman",
            "cour": "Courier New",
        }.get(str(self.family.currentData()), "Arial")
        weight = "700" if self.bold.isChecked() else "400"
        italic = "italic" if self.italic.isChecked() else "normal"
        alignment = ("left", "center", "right")[self.alignment.currentIndex()]
        background = (
            self._background_color.name()
            if self.background_enabled.isChecked()
            else "transparent"
        )
        safe = (
            self.editor.toPlainText()
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        self.preview.setText(
            f'<div style="padding:8px; font-family:{family}; font-size:{self.size.value()}pt; '
            f'font-weight:{weight}; font-style:{italic}; color:{self._text_color.name()}; '
            f'background:{background}; text-align:{alignment};">{safe}</div>'
        )

    @staticmethod
    def _font_variant(base: str, bold: bool, italic: bool) -> str:
        variants = {
            "helv": {
                (False, False): "helv",
                (True, False): "hebo",
                (False, True): "heit",
                (True, True): "hebi",
            },
            "tiro": {
                (False, False): "tiro",
                (True, False): "tibo",
                (False, True): "tiit",
                (True, True): "tibi",
            },
            "cour": {
                (False, False): "cour",
                (True, False): "cobo",
                (False, True): "coit",
                (True, True): "cobi",
            },
        }
        return variants.get(base, variants["helv"])[(bold, italic)]

    @staticmethod
    def _rgb(color: QColor) -> tuple[float, float, float]:
        return color.redF(), color.greenF(), color.blueF()

    @staticmethod
    def _contrast(color: QColor) -> str:
        return "#000000" if color.lightness() > 145 else "#ffffff"


class FileWorkspaceWidget(_ExpertFileWorkspaceWidget):
    """Localized production workspace with brush erasing and formatted PDF text."""

    def __init__(self, parent: QWidget | None = None, *, language: str = "ru") -> None:
        self.language = normalize_language(language)
        super().__init__(parent, language=self.language)
        self.document_service = EnhancedDocumentService()
        self._remove_legacy_text_and_combined_eraser()
        self._install_interactive_pdf_tools()
        self._widen_calculation_fields()
        self._localize_workspace()
        self._sync_document_state()

    def _t(self, key: str, **values: object) -> str:
        return text(self.language, key, **values)

    def _remove_legacy_text_and_combined_eraser(self) -> None:
        for button in list(self.findChildren(QToolButton)):
            label = button.text().replace("&", "")
            if label in {"Добавить текст", "Ластик / заменить"}:
                if button in self._pdf_tools:
                    self._pdf_tools.remove(button)
                button.hide()
                button.setParent(None)
                button.deleteLater()

    def _install_interactive_pdf_tools(self) -> None:
        context_bar = self.findChild(QFrame, "contextBar")
        layout = context_bar.layout() if context_bar is not None else None
        if not isinstance(layout, QHBoxLayout) or context_bar is None:
            return

        self.eraser_button = QToolButton(context_bar)
        self.eraser_button.setObjectName("pdfBrushEraserButton")
        self.eraser_button.setCheckable(True)
        self.eraser_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.eraser_button.toggled.connect(self._toggle_eraser)

        self.eraser_size_label = QLabel(context_bar)
        self.eraser_size = QSpinBox(context_bar)
        self.eraser_size.setObjectName("pdfEraserSize")
        self.eraser_size.setRange(8, 180)
        self.eraser_size.setValue(36)
        self.eraser_size.setSuffix(" px")
        self.eraser_size.setMinimumWidth(105)

        self.text_button = QToolButton(context_bar)
        self.text_button.setObjectName("pdfFormattedTextButton")
        self.text_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.text_button.clicked.connect(lambda: self._open_text_editor(replace=False))

        self.replace_text_button = QToolButton(context_bar)
        self.replace_text_button.setObjectName("pdfReplaceTextButton")
        self.replace_text_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.replace_text_button.clicked.connect(
            lambda: self._open_text_editor(replace=True)
        )

        insertion = 1
        layout.insertWidget(insertion, self.eraser_button)
        layout.insertWidget(insertion + 1, self.eraser_size_label)
        layout.insertWidget(insertion + 2, self.eraser_size)
        layout.insertWidget(insertion + 3, self.text_button)
        layout.insertWidget(insertion + 4, self.replace_text_button)
        self._pdf_tools.extend(
            [self.eraser_button, self.text_button, self.replace_text_button]
        )

        self._eraser_overlay = _EraserOverlay(self.document_canvas)
        self._eraser_overlay.setGeometry(self.document_canvas.rect())
        self._eraser_overlay.stroke_completed.connect(self._apply_eraser_stroke)
        self.eraser_size.valueChanged.connect(self._eraser_overlay.set_brush_size)
        self._eraser_overlay.set_brush_size(self.eraser_size.value())
        self._eraser_overlay.raise_()

    def _toggle_eraser(self, enabled: bool) -> None:
        if enabled and self.document_service.kind is not DocumentKind.PDF:
            self.eraser_button.blockSignals(True)
            self.eraser_button.setChecked(False)
            self.eraser_button.blockSignals(False)
            self._show_error(self._t("tool_eraser"), self._t("eraser_pdf_only"))
            return
        self._eraser_overlay.set_active(enabled)
        self.document_status.setText(
            self._t("eraser_active") if enabled else self._current_document_status()
        )

    def _apply_eraser_stroke(self, points: list[QPointF], brush_size: int) -> None:
        scale = max(self._render_zoom, 0.1)
        half = brush_size / (2.0 * scale)
        rects = [
            (
                point.x() / scale - half,
                point.y() / scale - half,
                point.x() / scale + half,
                point.y() / scale + half,
            )
            for point in points
        ]
        try:
            service = self._enhanced_service()
            service.erase_pdf_rects(rects)
            self._refresh_document()
            self.document_status.setText(self._t("eraser_done"))
        except DocumentError as error:
            self._show_error(self._t("tool_eraser"), error)

    def _open_text_editor(self, *, replace: bool) -> None:
        if self.document_service.kind is not DocumentKind.PDF:
            self._show_error(self._t("tool_text"), self._t("eraser_pdf_only"))
            return
        try:
            rect = self._selected_document_rect()
        except DocumentError:
            self._show_error(self._t("tool_text"), self._t("select_area_first"))
            return
        dialog = _PdfTextDialog(self.language, replace=replace, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        style = dialog.style()
        try:
            service = self._enhanced_service()
            service.add_styled_pdf_text(
                rect,
                style.text,
                fontname=style.fontname,
                font_size=style.font_size,
                color=style.color,
                alignment=style.alignment,
                background=style.background,
                replace=replace,
            )
            self._refresh_document()
            self.document_status.setText(
                self._t("text_replaced" if replace else "text_added")
            )
        except DocumentError as error:
            self._show_error(
                self._t("tool_replace_text" if replace else "tool_text"), error
            )

    def _enhanced_service(self) -> EnhancedDocumentService:
        if not isinstance(self.document_service, EnhancedDocumentService):
            raise DocumentError("Enhanced document service is unavailable")
        return self.document_service

    def _refresh_document(self) -> None:
        super()._refresh_document()
        overlay = getattr(self, "_eraser_overlay", None)
        if overlay is not None:
            overlay.setGeometry(self.document_canvas.rect())
            overlay.raise_()

    def _widen_calculation_fields(self) -> None:
        self.expression_input.setMinimumWidth(440)
        self.expression_result.setMinimumWidth(300)
        self.converter_value.setMinimumWidth(220)
        self.converter_result.setMinimumWidth(300)
        self.converter_category.setMinimumWidth(160)
        self.converter_source.setMinimumWidth(150)
        self.converter_target.setMinimumWidth(150)
        for control in self.findChildren(QDoubleSpinBox):
            control.setMinimumWidth(max(control.minimumWidth(), 175))
        for control in self.findChildren(QLineEdit):
            control.setMinimumHeight(max(control.minimumHeight(), 34))
        for label in self.findChildren(QLabel, "statusCard"):
            label.setMinimumWidth(360)
            label.setMinimumHeight(100)
        self.setStyleSheet(
            self.styleSheet()
            + "\nQLineEdit#resultField { min-width: 300px; }"
            + "\nQDoubleSpinBox { min-width: 175px; min-height: 34px; }"
            + "\nQLineEdit { min-height: 34px; }"
            + "\nQToolButton#pdfBrushEraserButton:checked { background: #b91c1c; color: white; border: 2px solid #ef4444; font-weight: 700; }"
        )

    def _localize_workspace(self) -> None:
        self.sections.setTabText(0, self._t("tab_documents"))
        self.sections.setTabText(1, self._t("tab_pdf"))
        self.sections.setTabText(2, self._t("tab_logo"))
        self.sections.setTabText(3, self._t("tab_archives"))
        self.sections.setTabText(4, self._t("tab_engineering"))
        for index, key in enumerate(
            (
                "tab_documents_tip",
                "tab_pdf_tip",
                "tab_logo_tip",
                "tab_archives_tip",
                "tab_engineering_tip",
            )
        ):
            self.sections.setTabToolTip(index, self._t(key))

        title = self.findChild(QLabel, "filesTitle")
        if title is not None:
            title.setText(self._t("workspace_title"))
        header = self.findChild(QFrame, "filesHeader")
        if header is not None:
            muted = [
                label
                for label in header.findChildren(QLabel)
                if label.objectName() == "muted"
            ]
            if muted:
                muted[0].setText(self._t("workspace_subtitle"))
            buttons = header.findChildren(QPushButton)
            if buttons:
                buttons[0].setText(self._t("open_document"))
            if len(buttons) > 1:
                buttons[1].setText(self._t("calculator"))

        cards = self.findChildren(QFrame, "expertHelpCard")
        card_keys = (
            ("help_documents_title", "help_documents_body"),
            ("help_pdf_title", "help_pdf_body"),
            ("help_logo_title", "help_logo_body"),
            ("help_archives_title", "help_archives_body"),
            ("help_engineering_title", "help_engineering_body"),
        )
        for card, (title_key, body_key) in zip(cards, card_keys, strict=False):
            labels = card.findChildren(QLabel)
            if labels:
                labels[0].setText(self._t(title_key))
            if len(labels) > 1:
                labels[1].setText(self._t(body_key))

        self.eraser_button.setText(self._t("tool_eraser"))
        self.eraser_button.setToolTip(self._t("tool_eraser_tip"))
        self.eraser_size_label.setText(self._t("eraser_size"))
        self.eraser_size.setToolTip(self._t("eraser_size_tip"))
        self.text_button.setText(self._t("tool_text"))
        self.text_button.setToolTip(self._t("tool_text_tip"))
        self.replace_text_button.setText(self._t("tool_replace_text"))
        self.replace_text_button.setToolTip(self._t("tool_replace_text_tip"))

        self.expression_input.setPlaceholderText(
            self._t("calculator_expression_placeholder")
        )
        self.expression_result.setPlaceholderText(self._t("result"))
        self.converter_result.setPlaceholderText(self._t("result"))
        self._localize_common_visible_strings()
        self._localize_side_panels()
        self._localize_categories()
        self._localize_datum()

    def _localize_common_visible_strings(self) -> None:
        replacements = self._legacy_replacements()
        for widget in self.findChildren(QLabel):
            translated = replacements.get(widget.text())
            if translated:
                widget.setText(translated)
        for widget in self.findChildren(QPushButton):
            translated = replacements.get(widget.text())
            if translated:
                widget.setText(translated)
        for widget in self.findChildren(QToolButton):
            translated = replacements.get(widget.text())
            if translated:
                widget.setText(translated)
        for widget in self.findChildren(QCheckBox):
            translated = replacements.get(widget.text())
            if translated:
                widget.setText(translated)
        for widget in self.findChildren(QGroupBox):
            translated = replacements.get(widget.title())
            if translated:
                widget.setTitle(translated)
        for widget in self.findChildren(QWidget):
            tip = widget.toolTip()
            if tip in replacements:
                widget.setToolTip(replacements[tip])
        for widget in self.findChildren(QLineEdit):
            placeholder = widget.placeholderText()
            if placeholder in replacements:
                widget.setPlaceholderText(replacements[placeholder])
        for widget in self.findChildren(QTextEdit):
            placeholder = widget.placeholderText()
            if placeholder in replacements:
                widget.setPlaceholderText(replacements[placeholder])

    def _legacy_replacements(self) -> dict[str, str]:
        if self.language == "ru":
            return {}
        kk = self.language == "kk"
        return {
            "Открыть": "Ашу" if kk else "Open",
            "Сохранить": "Сақтау" if kk else "Save",
            "Сохранить как": "Басқаша сақтау" if kk else "Save as",
            "Отменить": "Қайтару" if kk else "Undo",
            "Повторить": "Қайталау" if kk else "Redo",
            "Назад": "Артқа" if kk else "Previous",
            "Вперёд": "Алға" if kk else "Next",
            "По ширине": "Ені бойынша" if kk else "Fit width",
            "Вся страница": "Толық бет" if kk else "Fit page",
            "Инструменты:": "Құралдар:" if kk else "Tools:",
            "Выделить": "Белгілеу" if kk else "Highlight",
            "Примечание": "Ескертпе" if kk else "Note",
            "Безопасно скрыть": "Аймақты жою" if kk else "Redact area",
            "Удалить аннотации": "Аннотацияларды жою" if kk else "Delete annotations",
            "Размер": "Өлшем" if kk else "Resize",
            "Обрезать": "Қию" if kk else "Crop",
            "Коррекция": "Түзету" if kk else "Adjust",
            "Объединить PDF...": "PDF біріктіру..." if kk else "Merge PDF...",
            "Разделить PDF...": "PDF бөлу..." if kk else "Split PDF...",
            "Сохранить вид страниц...": (
                "Бет көрінісін сақтау..." if kk else "Preserve page appearance..."
            ),
            "Извлечь только текст...": (
                "Тек мәтінді шығару..." if kk else "Extract text only..."
            ),
            "Экспорт в Word:": "Word форматына экспорт:" if kk else "Export to Word:",
            "Архивы": "Мұрағаттар" if kk else "Archives",
            "Нефтегазовые расчёты": (
                "Мұнай-газ есептері" if kk else "Oilfield calculations"
            ),
            "Добавить файлы...": "Файлдарды қосу..." if kk else "Add files...",
            "Добавить папку...": "Буманы қосу..." if kk else "Add folder...",
            "Очистить": "Тазалау" if kk else "Clear",
            "Создать архив...": "Мұрағат жасау..." if kk else "Create archive...",
            "Показать состав архива...": (
                "Мұрағат құрамын көрсету..." if kk else "Inspect archive..."
            ),
            "Распаковать архив...": (
                "Мұрағатты ашу..." if kk else "Extract archive..."
            ),
            "Инженерный калькулятор": (
                "Инженерлік калькулятор" if kk else "Engineering calculator"
            ),
            "Конвертер единиц": (
                "Өлшем бірліктерін түрлендіру" if kk else "Unit converter"
            ),
            "Преобразовать": "Түрлендіру" if kk else "Convert",
            "Категория": "Санат" if kk else "Category",
            "Значение": "Мән" if kk else "Value",
            "Из": "Бастапқы" if kk else "From",
            "В": "Нәтиже бірлігі" if kk else "To",
            "Результат": "Нәтиже" if kk else "Result",
            "Трубы": "Құбырлар" if kk else "Pipes",
            "Бурение": "Бұрғылау" if kk else "Drilling",
            "Буровой раствор": (
                "Бұрғылау ерітіндісі" if kk else "Drilling fluid"
            ),
            "Геология": "Геология" if kk else "Geology",
            "Наружный диаметр, дюймы:": (
                "Сыртқы диаметр, дюйм:" if kk else "Outer diameter, inches:"
            ),
            "Толщина стенки:": "Қабырға қалыңдығы:" if kk else "Wall thickness:",
            "Длина:": "Ұзындығы:" if kk else "Length:",
            "Плотность материала:": (
                "Материал тығыздығы:" if kk else "Material density:"
            ),
            "Плотность раствора": "Ерітінді тығыздығы" if kk else "Fluid density",
            "Диаметр ствола": "Ұңғыма диаметрі" if kk else "Hole diameter",
            "Наружный диаметр трубы": (
                "Құбырдың сыртқы диаметрі" if kk else "Pipe outer diameter"
            ),
            "Длина интервала": "Интервал ұзындығы" if kk else "Interval length",
            "Расход насосов": "Сорғы шығыны" if kk else "Pump rate",
            "Потери давления в затрубье": (
                "Сақиналы кеңістіктегі қысым шығыны"
                if kk
                else "Annular pressure loss"
            ),
            "Объём 1": "1-көлем" if kk else "Volume 1",
            "Плотность 1": "1-тығыздық" if kk else "Density 1",
            "Объём 2": "2-көлем" if kk else "Volume 2",
            "Плотность 2": "2-тығыздық" if kk else "Density 2",
            "Абсолютная отметка datum:": (
                "Datum абсолюттік белгісі:" if kk else "Datum elevation:"
            ),
            "TVD кровли:": "Қабат төбесінің TVD:" if kk else "Top TVD:",
            "TVD подошвы:": "Қабат табанының TVD:" if kk else "Bottom TVD:",
            "Быстрые стили": "Жылдам стильдер" if kk else "Quick styles",
            "Прозрачный фон": "Мөлдір фон" if kk else "Transparent background",
        }

    def _localize_side_panels(self) -> None:
        side_panels = self.findChildren(QFrame, "sidePanel")
        if len(side_panels) >= 2:
            left_labels = side_panels[0].findChildren(QLabel)
            if left_labels:
                left_labels[0].setText(self._t("document"))
            if len(left_labels) > 2:
                left_labels[2].setText(self._t("pages"))
            right_labels = side_panels[1].findChildren(QLabel)
            if right_labels:
                right_labels[0].setText(self._t("quick_workflow"))
            if len(right_labels) > 1:
                right_labels[1].setText(self._t("workflow_steps"))
            if len(right_labels) > 2:
                right_labels[2].setText(self._t("selected_area"))
            if len(right_labels) > 3:
                right_labels[3].setText(self._t("no_area"))
            if len(right_labels) > 4:
                right_labels[4].setText(self._t("state"))
        self._document_info.setText(self._t("file_not_open"))
        self._selection_info.setText(self._t("no_area"))

    def _localize_categories(self) -> None:
        if self.language == "ru":
            return
        labels = {
            "length": "Ұзындық" if self.language == "kk" else "Length",
            "pressure": "Қысым" if self.language == "kk" else "Pressure",
            "temperature": "Температура" if self.language == "kk" else "Temperature",
            "area": "Аудан" if self.language == "kk" else "Area",
            "volume": "Көлем" if self.language == "kk" else "Volume",
            "mass": "Масса" if self.language == "kk" else "Mass",
            "force": "Күш" if self.language == "kk" else "Force",
            "torque": "Айналу моменті" if self.language == "kk" else "Torque",
            "density": "Тығыздық" if self.language == "kk" else "Density",
            "flow": "Шығын" if self.language == "kk" else "Flow rate",
        }
        for index in range(self.converter_category.count()):
            key = str(self.converter_category.itemData(index))
            if key in labels:
                self.converter_category.setItemText(index, labels[key])

    def _localize_datum(self) -> None:
        group = self.datum_inputs[0].parentWidget() if self.datum_inputs else None
        layout = group.layout() if group is not None else None
        if not isinstance(layout, QGridLayout) or self.language == "ru":
            return
        kk = self.language == "kk"
        if isinstance(group, QGroupBox):
            group.setTitle(
                "Бұрғылау қондырғысының биіктік белгілері"
                if kk
                else "Rig elevations and depth reference"
            )
        labels = (
            "Тірек абсолюттік белгі, м" if kk else "Reference elevation, m",
            (
                "GL жер деңгейінің тірек белгіге ығысуы, м"
                if kk
                else "Ground level GL offset from reference, m"
            ),
            (
                "Wellhead сағасының GL үстіндегі биіктігі, м"
                if kk
                else "Wellhead height above GL, m"
            ),
            (
                "DF бұрғылау еденінің GL үстіндегі биіктігі, м"
                if kk
                else "Drill floor DF height above GL, m"
            ),
            (
                "RT ротор үстелінің DF үстіндегі белгісі, м"
                if kk
                else "Rotary table RT elevation above DF, m"
            ),
            "KB/RKB биіктігі RT үстінде, м" if kk else "KB/RKB height above RT, m",
        )
        for row, label_text in enumerate(labels):
            item = layout.itemAtPosition(row, 0)
            label = item.widget() if item is not None else None
            if isinstance(label, QLabel):
                label.setText(label_text)

    def _current_document_status(self) -> str:
        if not self.document_service.is_open:
            return self._t("file_not_open")
        path = self.document_service.path
        return str(path) if path is not None else self._t("document")

    def _sync_document_state(self) -> None:
        super()._sync_document_state()
        if not self.document_service.is_open:
            self._document_info.setText(self._t("file_not_open"))
            return
        path = self.document_service.path
        kind = (
            "PDF"
            if self.document_service.kind is DocumentKind.PDF
            else self._t("image")
        )
        self._document_info.setText(
            self._t(
                "document_summary",
                name=f"<b>{path.name if path else self._t('document')}</b>",
                kind=kind,
                count=self.document_service.page_count,
            )
        )

    def _populate_page_list(self) -> None:
        from PySide6.QtWidgets import QListWidgetItem

        self._syncing_pages = True
        self._page_list.clear()
        count = self.document_service.page_count
        for page_index in range(count):
            item = QListWidgetItem(self._t("page", number=page_index + 1))
            item.setData(Qt.ItemDataRole.UserRole, page_index)
            item.setToolTip(self._t("go_page", number=page_index + 1))
            self._page_list.addItem(item)
        if count:
            self._page_list.setCurrentRow(self.document_service.page_index)
        self._syncing_pages = False
        self._load_visible_page_icons()

    def _selection_changed(self, selection: QRect) -> None:
        if selection.isNull() or selection.width() < 2 or selection.height() < 2:
            self._selection_info.setText(self._t("no_area"))
            return
        super()._selection_changed(selection)

    def _update_pipe_calculator(self, *_args: object) -> None:
        try:
            result = pipe_geometry(
                self.pipe_od_in.text(),
                self.pipe_wall_mm.value(),
                self.pipe_length_m.value(),
                self.pipe_density.value(),
            )
            self.pipe_result.setText(
                f"{self._t('pipe_outer')}: <b>{result.outer_diameter_mm:.3f} mm</b><br>"
                f"{self._t('pipe_inner')}: {result.inner_diameter_mm:.3f} mm<br>"
                f"{self._t('flow_area')}: {result.flow_area_mm2:.1f} mm²<br>"
                f"{self._t('capacity')}: {result.capacity_l_per_m:.3f} L/m<br>"
                f"{self._t('mass')}: {result.mass_kg_per_m:.3f} kg/m; "
                f"{self._t('total')} {result.total_mass_kg:.3f} kg"
            )
        except Exception as error:
            self.pipe_result.setText(self._t("invalid_data", error=error))

    def _update_drilling_calculator(self, *_args: object) -> None:
        try:
            pressure = hydrostatic_pressure(
                self.drill_mud_density.value(), self.drill_tvd.value()
            )
            annulus = annular_volume(
                self.drill_hole_d.value(),
                self.drill_pipe_d.value(),
                self.drill_interval.value(),
            )
            minutes = circulation_time_minutes(
                annulus.volume_m3, self.drill_flow.value()
            )
            self.drill_result.setText(
                f"{self._t('hydrostatic_pressure')}: <b>{pressure.pressure_mpa:.3f} MPa</b> "
                f"({pressure.pressure_psi:.1f} psi)<br>"
                f"{self._t('gradient')}: {pressure.gradient_kpa_per_m:.4f} kPa/m<br>"
                f"{self._t('annular_capacity')}: {annulus.capacity_l_per_m:.3f} L/m<br>"
                f"{self._t('interval_volume')}: {annulus.volume_m3:.3f} m³ "
                f"({annulus.volume_l:.1f} L)<br>"
                f"{self._t('circulation_time')}: {minutes:.2f} min"
            )
        except Exception as error:
            self.drill_result.setText(self._t("invalid_data", error=error))

    def _update_mud_calculator(self, *_args: object) -> None:
        try:
            ecd = equivalent_circulating_density(
                self.mud_density.value(),
                self.mud_annular_loss.value(),
                self.mud_tvd.value(),
            )
            mixture = mixed_fluid_density(
                self.mix_v1.value(),
                self.mix_rho1.value(),
                self.mix_v2.value(),
                self.mix_rho2.value(),
            )
            self.mud_result.setText(
                f"ECD: <b>{ecd:.2f} kg/m³</b> ({ecd / 119.826427316:.3f} ppg)<br>"
                f"{self._t('mixture_density')}: <b>{mixture:.2f} kg/m³</b><br>"
                f"{self._t('ecd_note')}"
            )
        except Exception as error:
            self.mud_result.setText(self._t("invalid_data", error=error))

    def _update_geology_calculator(self, *_args: object) -> None:
        try:
            result = formation_elevations(
                self.geo_reference.value(),
                self.geo_top_tvd.value(),
                self.geo_bottom_tvd.value(),
            )
            self.geo_result.setText(
                f"{self._t('formation_top')}: <b>{result.top_elevation_m:.3f} m</b><br>"
                f"{self._t('formation_bottom')}: <b>{result.bottom_elevation_m:.3f} m</b><br>"
                f"{self._t('vertical_thickness')}: {result.vertical_thickness_m:.3f} m"
            )
        except Exception as error:
            self.geo_result.setText(self._t("invalid_data", error=error))

    def _install_main_toolbar_entry(self) -> None:
        super()._install_main_toolbar_entry()
        window: Any = self.window()
        action = getattr(window, "file_workspace_action", None)
        if action is not None:
            action.setText(self._t("toolbar_files"))
            action.setToolTip(self._t("toolbar_files_tip"))
