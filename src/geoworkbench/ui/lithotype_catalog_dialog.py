from __future__ import annotations

from collections.abc import Callable
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.tablet.lithology_patterns import lithology_brush, supported_pattern_keys
from geoworkbench.ui.lithotype_visuals import lithotype_icon, pattern_icon


class LithologyPatternPreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = "#c9a66b"
        self._pattern_key = "solid"
        self.setMinimumHeight(64)
        self.setObjectName("lithology-pattern-preview")

    def set_pattern(self, color: str, pattern_key: str) -> None:
        self._color = color
        self._pattern_key = pattern_key
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#404040"), 1))
        painter.setBrush(lithology_brush(self._color, self._pattern_key))
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
        painter.end()
        super().paintEvent(event)


class LithotypeCatalogDialog(QDialog):
    def __init__(
        self,
        controller: LithotypeCatalogController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.language = language
        self.controller = controller
        self.setWindowTitle(self._t("catalog.window_title"))
        self.resize(1100, 620)

        root = QVBoxLayout(self)
        info = QLabel(
            {
                AppLanguage.RU: (
                    "Стандартный набор включает встроенные обозначения и 117 переданных "
                    "литологических рисунков. Заводскую запись можно изменить: программа "
                    "создаст проектное переопределение, которое затем можно сбросить."
                ),
                AppLanguage.KK: (
                    "Стандартты жинақта кірістірілген белгілер және берілген 117 литологиялық "
                    "сурет бар. Зауыттық жазбаны өзгерткенде жобалық қайта анықтау жасалады."
                ),
                AppLanguage.EN: (
                    "The standard set contains the built-in symbols and all 117 supplied "
                    "lithology bitmaps. Editing a factory row creates a project override that "
                    "can later be reset."
                ),
            }[language]
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            {
                AppLanguage.RU: "Поиск по коду, названию, ID, псевдониму или рисунку...",
                AppLanguage.KK: "Код, атау, ID, бүркеншік ат немесе сурет бойынша іздеу...",
                AppLanguage.EN: "Search by code, name, ID, alias or pattern...",
            }[language]
        )
        self.search_input.textChanged.connect(self._apply_filter)
        root.addWidget(self.search_input)
        self.table = QTableWidget(0, 9)
        self.table.setObjectName("lithotype-catalog-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("catalog.source"),
                self._t("catalog.code"),
                self._t("catalog.id"),
                self._t("catalog.name_ru"),
                self._t("catalog.name_kk"),
                self._t("catalog.name_en"),
                self._t("catalog.category"),
                self._t("catalog.color"),
                self._t("catalog.pattern"),
            ]
        )
        self.table.itemSelectionChanged.connect(self._load_selected)
        root.addWidget(self.table)

        form = QFormLayout()
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText(self._t("catalog.id_example"))
        self.code_input = QLineEdit()
        self.name_ru_input = QLineEdit()
        self.name_kk_input = QLineEdit()
        self.name_en_input = QLineEdit()
        self.category_input = QLineEdit()
        self.color_input = QLineEdit("#c9a66b")
        self.pattern_input = QComboBox()
        self.pattern_input.setEditable(True)
        for pattern_key in supported_pattern_keys():
            self.pattern_input.addItem(
                pattern_icon("#f8fafc", pattern_key),
                pattern_key,
                pattern_key,
            )
        for label, field in (
            (self._t("catalog.id"), self.id_input),
            (self._t("catalog.code"), self.code_input),
            (self._t("catalog.name_ru"), self.name_ru_input),
            (self._t("catalog.name_kk"), self.name_kk_input),
            (self._t("catalog.name_en"), self.name_en_input),
            (self._t("catalog.category"), self.category_input),
            (self._t("catalog.pattern_key"), self.pattern_input),
        ):
            form.addRow(label, field)
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.color_input)
        self.color_button = QPushButton(self._t("common.choose"))
        self.color_button.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_button)
        form.addRow(self._t("catalog.color_hex"), color_row)
        self.pattern_preview = LithologyPatternPreview()
        form.addRow(self._t("catalog.preview"), self.pattern_preview)
        self.color_input.textChanged.connect(self._update_preview)
        self.pattern_input.currentTextChanged.connect(self._update_preview)
        root.addLayout(form)

        actions = QHBoxLayout()
        for object_name, title, handler in (
            ("catalog-new-button", self._t("catalog.new"), self._clear_form),
            ("catalog-add-button", self._t("common.add"), self._add),
            ("catalog-update-button", self._t("common.update"), self._update),
            (
                "catalog-remove-button",
                {
                    AppLanguage.RU: "Сбросить / удалить",
                    AppLanguage.KK: "Қалпына келтіру / жою",
                    AppLanguage.EN: "Reset / delete",
                }[language],
                self._remove,
            ),
        ):
            button = QPushButton(title)
            button.setObjectName(object_name)
            button.clicked.connect(handler)
            actions.addWidget(button)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()
        self._update_preview()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _refresh(self) -> None:
        records = self.controller.available()
        self._records = records
        self._record_by_id = {record.lithotype_id: record for record in records}
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            if record.overridden:
                source = {
                    AppLanguage.RU: "Переопределён в проекте",
                    AppLanguage.KK: "Жобада қайта анықталған",
                    AppLanguage.EN: "Project override",
                }[self.language]
            elif record.source == "factory":
                source = {
                    AppLanguage.RU: "Стандартный рисунок",
                    AppLanguage.KK: "Стандартты сурет",
                    AppLanguage.EN: "Standard bitmap",
                }[self.language]
            elif record.system:
                source = self._t("catalog.system")
            else:
                source = self._t("catalog.project")
            values = (
                source,
                record.code,
                record.lithotype_id,
                record.name_ru,
                record.name_kk,
                record.name_en,
                record.category,
                record.color,
                record.pattern_key,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, record.lithotype_id)
                item.setData(Qt.ItemDataRole.UserRole + 1, record.system)
                item.setData(Qt.ItemDataRole.UserRole + 2, record.overridden)
                if column == 0:
                    item.setIcon(lithotype_icon(record))
                self.table.setItem(row, column, item)
            self.table.setRowHeight(row, 30)
        self.table.resizeColumnsToContents()
        self._apply_filter(self.search_input.text())

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        values = [self.table.item(row, column) for column in range(9)]
        if any(item is None for item in values):
            return
        source, code, lithotype_id, name_ru, name_kk, name_en, category, color, pattern = (
            cast(QTableWidgetItem, item) for item in values
        )
        self.id_input.setText(lithotype_id.text())
        self.id_input.setReadOnly(True)
        self.code_input.setText(code.text())
        self.name_ru_input.setText(name_ru.text())
        self.name_kk_input.setText(name_kk.text())
        self.name_en_input.setText(name_en.text())
        self.category_input.setText(category.text())
        self.color_input.setText(color.text())
        self.pattern_input.setCurrentText(pattern.text())

    def _clear_form(self) -> None:
        self.table.clearSelection()
        self.id_input.setReadOnly(False)
        for field in (
            self.id_input,
            self.code_input,
            self.name_ru_input,
            self.name_kk_input,
            self.name_en_input,
            self.category_input,
        ):
            field.clear()
        self.pattern_input.setCurrentText("solid")
        self.color_input.setText("#c9a66b")
        self.id_input.setFocus()

    def _values(self) -> tuple[str, str, str, str, str, str, str, str]:
        return (
            self.id_input.text(),
            self.code_input.text(),
            self.name_ru_input.text(),
            self.name_en_input.text(),
            self.category_input.text(),
            self.color_input.text(),
            self.pattern_input.currentText(),
            self.name_kk_input.text(),
        )

    def _choose_color(self) -> None:
        initial = QColor(self.color_input.text())
        selected = QColorDialog.getColor(initial, self, self._t("catalog.color_title"))
        if selected.isValid():
            self.color_input.setText(selected.name())

    def _update_preview(self) -> None:
        self.pattern_preview.set_pattern(self.color_input.text(), self.pattern_input.currentText())

    def _add(self) -> None:
        self._run(lambda: self.controller.add(*self._values()))

    def _update(self) -> None:
        lithotype_id = self._selected_id()
        if lithotype_id is None:
            QMessageBox.information(
                self, self._t("catalog.title"), self._t("catalog.select_project")
            )
            return
        _, code, name_ru, name_en, category, color, pattern, name_kk = self._values()
        self._run(
            lambda: self.controller.update(
                lithotype_id,
                code=code,
                name_ru=name_ru,
                name_en=name_en,
                category=category,
                color=color,
                pattern_key=pattern,
                name_kk=name_kk,
            )
        )

    def _remove(self) -> None:
        lithotype_id = self._selected_id()
        if lithotype_id is None:
            QMessageBox.information(
                self, self._t("catalog.title"), self._t("catalog.select_project")
            )
            return
        self._run(lambda: self.controller.remove(lithotype_id))

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _apply_filter(self, query: str) -> None:
        needle = query.strip().casefold()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            lithotype_id = str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else ""
            record = getattr(self, "_record_by_id", {}).get(lithotype_id)
            if record is None or not needle:
                self.table.setRowHidden(row, False)
                continue
            values = (
                record.lithotype_id,
                record.code,
                record.name_ru,
                record.name_kk,
                record.name_en,
                record.category,
                record.pattern_key,
                *record.aliases,
            )
            self.table.setRowHidden(
                row,
                not any(needle in str(value).casefold() for value in values),
            )

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self._t("catalog.title"), str(exc))
            return False
        self._refresh()
        return True
