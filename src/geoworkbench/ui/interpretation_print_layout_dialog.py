from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QPageLayout
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.services.localization import AppLanguage


class InterpretationPrintOrder(str, Enum):
    FIRST_TO_LAST = "first-to-last"
    LAST_TO_FIRST = "last-to-first"


@dataclass(frozen=True, slots=True)
class InterpretationPrintLayout:
    orientation: QPageLayout.Orientation
    order: InterpretationPrintOrder


class InterpretationPrintLayoutDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        include_order: bool = True,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.include_order = include_order
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setWindowTitle(
            self._text(
                "Макет печати отчёта" if include_order else "Макет PDF-отчёта",
                "Есепті басып шығару макеті" if include_order else "PDF есеп макеті",
                "Report print layout" if include_order else "PDF report layout",
            )
        )

        root = QVBoxLayout(self)
        description = QLabel(
            self._description_text()
        )
        description.setWordWrap(True)
        root.addWidget(description)

        form = QFormLayout()
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem(
            self._text(
                "Книжная — формы и страницы адаптируются по ширине",
                "Кітапша — пішіндер мен беттер еніне бейімделеді",
                "Portrait — forms and pages adapt to the width",
            ),
            QPageLayout.Orientation.Portrait,
        )
        self.orientation_combo.addItem(
            self._text(
                "Альбомная — больше места для графиков и таблиц",
                "Альбомдық — графиктер мен кестелерге көбірек орын",
                "Landscape — more room for charts and tables",
            ),
            QPageLayout.Orientation.Landscape,
        )
        self.order_combo = QComboBox()
        self.order_combo.addItem(
            self._text(
                "С первой страницы к последней",
                "Бірінші беттен соңғы бетке дейін",
                "First page to last page",
            ),
            InterpretationPrintOrder.FIRST_TO_LAST,
        )
        self.order_combo.addItem(
            self._text(
                "С последней страницы к первой",
                "Соңғы беттен бірінші бетке дейін",
                "Last page to first page",
            ),
            InterpretationPrintOrder.LAST_TO_FIRST,
        )
        self.orientation_label = QLabel(
            self._text("Ориентация:", "Бағдар:", "Orientation:")
        )
        self.order_label = QLabel(
            self._text("Порядок:", "Реті:", "Order:")
        )
        form.addRow(self.orientation_label, self.orientation_combo)
        form.addRow(self.order_label, self.order_combo)
        self.order_label.setVisible(include_order)
        self.order_combo.setVisible(include_order)
        root.addLayout(form)

        note = QLabel(self._note_text())
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_layout(self) -> InterpretationPrintLayout:
        orientation = self.orientation_combo.currentData()
        order = self.order_combo.currentData()
        if not isinstance(orientation, QPageLayout.Orientation):
            orientation = QPageLayout.Orientation.Portrait
        if not self.include_order or not isinstance(order, InterpretationPrintOrder):
            order = InterpretationPrintOrder.FIRST_TO_LAST
        return InterpretationPrintLayout(orientation, order)

    def _description_text(self) -> str:
        if not self.include_order:
            return self._text(
                "Выберите ориентацию PDF. Титульный лист, графики, таблицы и "
                "страницы продолжения будут перестроены под выбранный формат.",
                "PDF бағдарын таңдаңыз. Титулдық бет, графиктер, кестелер және "
                "жалғастыру беттері таңдалған пішімге қайта құрылады.",
                "Choose the PDF orientation. The cover, charts, tables, and "
                "continuation pages will be rebuilt for the selected format.",
            )
        return self._text(
            "Сначала выберите макет отчёта. Диапазон страниц, принтер, "
            "число копий и свойства Epson будут доступны в следующем "
            "системном окне Windows.",
            "Алдымен есеп макетін таңдаңыз. Бет ауқымы, принтер, көшірме "
            "саны және Epson қасиеттері келесі Windows жүйелік терезесінде "
            "қолжетімді болады.",
            "Choose the report layout first. Page range, printer, copy count, "
            "and Epson properties remain available in the next Windows dialog.",
        )

    def _note_text(self) -> str:
        if not self.include_order:
            return self._text(
                "Книжная ориентация удобнее для последовательного чтения; "
                "альбомная оставляет больше ширины для графиков и таблиц.",
                "Кітапша бағдары ретімен оқуға ыңғайлы; альбомдық бағдар "
                "графиктер мен кестелерге көбірек ен қалдырады.",
                "Portrait is easier for sequential reading; landscape leaves "
                "more width for charts and tables.",
            )
        return self._text(
            "По умолчанию используется книжная ориентация и печать с "
            "первой страницы. Выбор диапазона 1–2 будет отправлять Epson "
            "только две выбранные страницы.",
            "Әдепкіде кітапша бағыты және бірінші беттен басып шығару "
            "қолданылады. 1–2 ауқымы Epson принтеріне тек екі бетті жібереді.",
            "Portrait and first-to-last are the defaults. Selecting pages "
            "1–2 sends only those two pages to Epson.",
        )

    def _text(self, ru: str, kk: str, en: str) -> str:
        if self.language is AppLanguage.KK:
            return kk
        if self.language is AppLanguage.EN:
            return en
        return ru


__all__ = [
    "InterpretationPrintLayout",
    "InterpretationPrintLayoutDialog",
    "InterpretationPrintOrder",
]
