from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.rich_interval_text_editor import RichIntervalTextEditor


_TEXT = {
    AppLanguage.RU: {
        "create": "Новое описание пород",
        "edit": "Редактирование описания пород",
        "interval": "Интервал описания",
        "top": "От, м",
        "bottom": "До, м",
        "hint": (
            "Введите текст вручную или вставьте содержимое из Word/Excel. "
            "Поддерживаются шрифты, цвет, выделение, символы и изображения."
        ),
        "delete": "Удалить пробу",
        "interval_error": "Начальная глубина должна быть меньше конечной.",
        "text_error": "Введите описание пород или шлама.",
    },
    AppLanguage.KK: {
        "create": "Жыныстардың жаңа сипаттамасы",
        "edit": "Жыныстар сипаттамасын өңдеу",
        "interval": "Сипаттама аралығы",
        "top": "Бастап, м",
        "bottom": "Дейін, м",
        "hint": (
            "Мәтінді қолмен енгізіңіз немесе Word/Excel ішінен қойыңыз. "
            "Қаріп, түс, белгілеу, таңбалар және суреттер сақталады."
        ),
        "delete": "Сынаманы жою",
        "interval_error": "Бастапқы тереңдік соңғы тереңдіктен кіші болуы тиіс.",
        "text_error": "Жыныс немесе шлам сипаттамасын енгізіңіз.",
    },
    AppLanguage.EN: {
        "create": "New rock description",
        "edit": "Edit rock description",
        "interval": "Description interval",
        "top": "From, m",
        "bottom": "To, m",
        "hint": (
            "Type text or paste content from Word/Excel. Fonts, colors, highlighting, "
            "symbols and embedded images are preserved."
        ),
        "delete": "Delete sample",
        "interval_error": "The start depth must be less than the end depth.",
        "text_error": "Enter a rock or cuttings description.",
    },
}


class RockDescriptionDialog(QDialog):
    """Edit one interval description without forcing a rock composition.

    A description may be entered before the laboratory/sample composition is
    known.  It is stored in the same ``CuttingsSample`` object, so later opening
    the full sample editor preserves the rich text and embedded images.
    """

    def __init__(
        self,
        top_depth: float,
        bottom_depth: float,
        *,
        language: AppLanguage,
        sample: CuttingsSample | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = _TEXT[language]
        self._sample = sample
        self.delete_requested = False
        self.setWindowTitle(self._text["edit"] if sample is not None else self._text["create"])
        self.setMinimumSize(560, 430)

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)

        interval_group = QGroupBox(self._text["interval"])
        interval_form = QFormLayout(interval_group)
        self.top_input = self._depth_input(top_depth)
        self.top_input.setObjectName("rock-description-top")
        self.bottom_input = self._depth_input(bottom_depth)
        self.bottom_input.setObjectName("rock-description-bottom")
        interval_form.addRow(self._text["top"], self.top_input)
        interval_form.addRow(self._text["bottom"], self.bottom_input)
        content_layout.addWidget(interval_group)

        hint = QLabel(self._text["hint"])
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "QLabel {background:#e0f2fe; color:#0c4a6e; border:1px solid #7dd3fc; "
            "border-radius:4px; padding:7px;}"
        )
        content_layout.addWidget(hint)

        self.editor = RichIntervalTextEditor(language=language)
        self.editor.set_html(sample.description if sample is not None else None)
        content_layout.addWidget(self.editor, 1)

        self.validation_label = QLabel()
        self.validation_label.setObjectName("rock-description-validation")
        self.validation_label.setStyleSheet("color:#dc2626; font-weight:600;")
        self.validation_label.setWordWrap(True)
        content_layout.addWidget(self.validation_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        if sample is not None:
            delete_button = buttons.addButton(
                self._text["delete"], QDialogButtonBox.ButtonRole.DestructiveRole
            )
            delete_button.setObjectName("rock-description-delete")
            delete_button.clicked.connect(self._delete)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)
        self._apply_adaptive_size()

    @staticmethod
    def _depth_input(value: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(-100_000.0, 100_000.0)
        control.setDecimals(3)
        control.setSuffix(" m")
        control.setValue(float(value))
        return control

    def _apply_adaptive_size(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(820, 650)
            return
        available = screen.availableGeometry()
        self.resize(
            min(920, max(560, int(available.width() * 0.72))),
            min(780, max(430, int(available.height() * 0.78))),
        )

    @property
    def top_depth(self) -> float:
        return float(self.top_input.value())

    @property
    def bottom_depth(self) -> float:
        return float(self.bottom_input.value())

    @property
    def description_html(self) -> str | None:
        value = self.editor.html()
        return value if value and self.editor.editor.toPlainText().strip() else None

    def _accept_if_valid(self) -> None:
        self.validation_label.clear()
        if self.top_depth >= self.bottom_depth:
            self.validation_label.setText(self._text["interval_error"])
            self.top_input.setFocus()
            return
        if self._sample is None and self.description_html is None:
            self.validation_label.setText(self._text["text_error"])
            self.editor.editor.setFocus()
            return
        self.accept()

    def _delete(self) -> None:
        self.delete_requested = True
        self.accept()
