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
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setWindowTitle(
            self._text(
                "Макет печати отчёта",
                "Есепті басып шығару макеті",
                "Report print layout",
            )
        )

        root = QVBoxLayout(self)
        description = QLabel(
            self._text(
                "Сначала выберите макет отчёта. Диапазон страниц, принтер, "
                "число копий и свойства Epson будут доступны в следующем "
                "системном окне Windows.",
                "Алдымен есеп макетін таңдаңыз. Бет ауқымы, принтер, көшірме "
                "саны және Epson қасиеттері келесі Windows жүйелік терезесінде "
                "қолжетімді болады.",
                "Choose the report layout first. Page range, printer, copy count, "
                "and Epson properties remain available in the next Windows dialog.",
            )
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
        form.addRow(
            self._text("Ориентация:", "Бағдар:", "Orientation:"),
            self.orientation_combo,
        )
        form.addRow(
            self._text("Порядок:", "Реті:", "Order:"),
            self.order_combo,
        )
        root.addLayout(form)

        note = QLabel(
            self._text(
                "По умолчанию используется книжная ориентация и печать с "
                "первой страницы. Выбор диапазона 1–2 будет отправлять Epson "
                "только две выбранные страницы.",
                "Әдепкіде кітапша бағыты және бірінші беттен басып шығару "
                "қолданылады. 1–2 ауқымы Epson принтеріне тек екі бетті жібереді.",
                "Portrait and first-to-last are the defaults. Selecting pages "
                "1–2 sends only those two pages to Epson.",
            )
        )
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
        if not isinstance(order, InterpretationPrintOrder):
            order = InterpretationPrintOrder.FIRST_TO_LAST
        return InterpretationPrintLayout(orientation, order)

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
