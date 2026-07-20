from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextBlockFormat, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFontComboBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.services.localization import AppLanguage


_TEXT = {
    AppLanguage.RU: {
        "bold": "Ж",
        "italic": "К",
        "underline": "Ч",
        "color": "Цвет",
        "highlight": "Фон",
        "superscript": "x²",
        "subscript": "x₂",
        "align_left": "По левому краю",
        "align_center": "По центру",
        "align_right": "По правому краю",
        "symbol": "Символ",
        "image": "Изображение",
        "placeholder": "Введите описание вручную или вставьте текст из Excel…",
    },
    AppLanguage.KK: {
        "bold": "Ж",
        "italic": "К",
        "underline": "А",
        "color": "Түс",
        "highlight": "Фон",
        "superscript": "x²",
        "subscript": "x₂",
        "align_left": "Сол жақ",
        "align_center": "Ортаға",
        "align_right": "Оң жақ",
        "symbol": "Таңба",
        "image": "Сурет",
        "placeholder": "Сипаттаманы енгізіңіз немесе Excel-ден мәтінді қойыңыз…",
    },
    AppLanguage.EN: {
        "bold": "B",
        "italic": "I",
        "underline": "U",
        "color": "Color",
        "highlight": "Highlight",
        "superscript": "x²",
        "subscript": "x₂",
        "align_left": "Align left",
        "align_center": "Align center",
        "align_right": "Align right",
        "symbol": "Symbol",
        "image": "Image",
        "placeholder": "Type a description or paste text from Excel…",
    },
}

_SYMBOLS = (
    "°",
    "±",
    "≤",
    "≥",
    "≈",
    "→",
    "←",
    "↑",
    "↓",
    "Ø",
    "Δ",
    "Σ",
    "CaCO₃",
    "CaMg(CO₃)₂",
    "CO₂",
    "H₂S",
    "C₁",
    "C₂",
    "C₃",
    "C₄",
    "C₅",
)


class RichIntervalTextEditor(QWidget):
    """Rich-text editor for interval descriptions stored inside the project.

    Formatting is serialized as HTML. Images are embedded as data URIs so a
    project remains self-contained when copied to another computer.
    """

    def __init__(self, *, language: AppLanguage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = _TEXT[language]
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(True)
        self.editor.setPlaceholderText(self._text["placeholder"])
        self.editor.setObjectName("interval-rich-text-editor")

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        self.font_input = QFontComboBox()
        self.font_input.currentFontChanged.connect(self._set_font_family)
        toolbar.addWidget(self.font_input)

        self.size_input = QSpinBox()
        self.size_input.setRange(6, 72)
        self.size_input.setValue(10)
        self.size_input.setSuffix(" pt")
        self.size_input.valueChanged.connect(self._set_font_size)
        toolbar.addWidget(self.size_input)

        self.bold_button = self._format_button(self._text["bold"], "bold")
        self.italic_button = self._format_button(self._text["italic"], "italic")
        self.underline_button = self._format_button(self._text["underline"], "underline")
        for button in (self.bold_button, self.italic_button, self.underline_button):
            toolbar.addWidget(button)

        color_button = QPushButton(self._text["color"])
        color_button.setObjectName("rich-text-color")
        color_button.clicked.connect(self._choose_color)
        toolbar.addWidget(color_button)

        highlight_button = QPushButton(self._text["highlight"])
        highlight_button.setObjectName("rich-text-highlight")
        highlight_button.clicked.connect(self._choose_highlight)
        toolbar.addWidget(highlight_button)

        self.superscript_button = self._script_button(
            self._text["superscript"], QTextCharFormat.VerticalAlignment.AlignSuperScript
        )
        self.superscript_button.setObjectName("rich-text-superscript")
        self.subscript_button = self._script_button(
            self._text["subscript"], QTextCharFormat.VerticalAlignment.AlignSubScript
        )
        self.subscript_button.setObjectName("rich-text-subscript")
        toolbar.addWidget(self.superscript_button)
        toolbar.addWidget(self.subscript_button)

        for text, alignment, name in (
            ("≡L", Qt.AlignmentFlag.AlignLeft, "left"),
            ("≡C", Qt.AlignmentFlag.AlignHCenter, "center"),
            ("R≡", Qt.AlignmentFlag.AlignRight, "right"),
        ):
            button = QToolButton()
            button.setText(text)
            button.setObjectName(f"rich-text-align-{name}")
            button.setToolTip(self._text[f"align_{name}"])
            button.clicked.connect(
                lambda _checked=False, selected=alignment: self._set_alignment(selected)
            )
            toolbar.addWidget(button)

        self.symbol_input = QComboBox()
        self.symbol_input.addItem(self._text["symbol"], "")
        for symbol in _SYMBOLS:
            self.symbol_input.addItem(symbol, symbol)
        self.symbol_input.activated.connect(self._insert_symbol)
        toolbar.addWidget(self.symbol_input)

        image_button = QPushButton(self._text["image"])
        image_button.clicked.connect(self._insert_image)
        toolbar.addWidget(image_button)
        toolbar.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(self.editor, 1)

    def _format_button(self, text: str, mode: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setCheckable(True)
        button.toggled.connect(
            lambda enabled, selected=mode: self._toggle_format(selected, enabled)
        )
        return button

    def _merge_format(self, fmt: QTextCharFormat) -> None:
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def _toggle_format(self, mode: str, enabled: bool) -> None:
        fmt = QTextCharFormat()
        if mode == "bold":
            fmt.setFontWeight(QFont.Weight.Bold if enabled else QFont.Weight.Normal)
        elif mode == "italic":
            fmt.setFontItalic(enabled)
        elif mode == "underline":
            fmt.setFontUnderline(enabled)
        self._merge_format(fmt)

    def _set_font_family(self, font: QFont) -> None:
        fmt = QTextCharFormat()
        fmt.setFontFamilies([font.family()])
        self._merge_format(fmt)

    def _set_font_size(self, size: int) -> None:
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        self._merge_format(fmt)

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(parent=self)
        if not color.isValid():
            return
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        self._merge_format(fmt)

    def _choose_highlight(self) -> None:
        color = QColorDialog.getColor(parent=self)
        if not color.isValid():
            return
        fmt = QTextCharFormat()
        fmt.setBackground(color)
        self._merge_format(fmt)

    def _script_button(
        self,
        text: str,
        alignment: QTextCharFormat.VerticalAlignment,
    ) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setCheckable(True)
        button.toggled.connect(
            lambda enabled, selected=alignment: self._toggle_script(selected, enabled)
        )
        return button

    def _toggle_script(
        self,
        alignment: QTextCharFormat.VerticalAlignment,
        enabled: bool,
    ) -> None:
        if enabled:
            other = (
                self.subscript_button
                if alignment == QTextCharFormat.VerticalAlignment.AlignSuperScript
                else self.superscript_button
            )
            other.blockSignals(True)
            other.setChecked(False)
            other.blockSignals(False)
        fmt = QTextCharFormat()
        fmt.setVerticalAlignment(
            alignment if enabled else QTextCharFormat.VerticalAlignment.AlignNormal
        )
        self._merge_format(fmt)

    def _set_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        cursor = self.editor.textCursor()
        block_format = QTextBlockFormat()
        block_format.setAlignment(alignment)
        cursor.mergeBlockFormat(block_format)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _insert_symbol(self, index: int) -> None:
        symbol = self.symbol_input.itemData(index)
        if isinstance(symbol, str) and symbol:
            self.editor.textCursor().insertText(symbol)
        self.symbol_input.setCurrentIndex(0)
        self.editor.setFocus()

    def _insert_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self._text["image"],
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not filename:
            return
        path = Path(filename)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        self.editor.textCursor().insertHtml(
            f'<img src="data:{mime};base64,{encoded}" style="max-width:100%; height:auto;" />'
        )

    def set_html(self, value: str | None) -> None:
        text = value or ""
        if "<" in text and ">" in text:
            self.editor.setHtml(text)
        else:
            self.editor.setPlainText(text)

    def html(self) -> str | None:
        html = self.editor.toHtml()
        if not self.editor.toPlainText().strip() and "<img" not in html.casefold():
            return None
        return html
