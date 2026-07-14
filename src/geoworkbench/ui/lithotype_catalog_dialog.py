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
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.tablet.lithology_patterns import lithology_brush, supported_pattern_keys


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
        self, controller: LithotypeCatalogController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Справочник пород и литотипов")
        self.resize(1100, 620)

        root = QVBoxLayout(self)
        self.table = QTableWidget(0, 8)
        self.table.setObjectName("lithotype-catalog-table")
        self.table.setHorizontalHeaderLabels(
            ["Источник", "Код", "ID", "Название", "Name", "Категория", "Цвет", "Узор"]
        )
        self.table.itemSelectionChanged.connect(self._load_selected)
        root.addWidget(self.table)

        form = QFormLayout()
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("например, oil_sand")
        self.code_input = QLineEdit()
        self.name_ru_input = QLineEdit()
        self.name_en_input = QLineEdit()
        self.category_input = QLineEdit()
        self.color_input = QLineEdit("#c9a66b")
        self.pattern_input = QComboBox()
        self.pattern_input.setEditable(True)
        self.pattern_input.addItems(supported_pattern_keys())
        for label, field in (
            ("ID", self.id_input),
            ("Код", self.code_input),
            ("Название (RU)", self.name_ru_input),
            ("Название (EN)", self.name_en_input),
            ("Категория", self.category_input),
            ("Ключ узора", self.pattern_input),
        ):
            form.addRow(label, field)
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.color_input)
        self.color_button = QPushButton("Выбрать...")
        self.color_button.clicked.connect(self._choose_color)
        color_layout.addWidget(self.color_button)
        form.addRow("Цвет #RRGGBB", color_row)
        self.pattern_preview = LithologyPatternPreview()
        form.addRow("Предпросмотр", self.pattern_preview)
        self.color_input.textChanged.connect(self._update_preview)
        self.pattern_input.currentTextChanged.connect(self._update_preview)
        root.addLayout(form)

        actions = QHBoxLayout()
        for title, handler in (
            ("Новая запись", self._clear_form),
            ("Добавить", self._add),
            ("Изменить", self._update),
            ("Удалить", self._remove),
        ):
            button = QPushButton(title)
            button.clicked.connect(handler)
            actions.addWidget(button)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()
        self._update_preview()

    def _refresh(self) -> None:
        records = self.controller.available()
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = (
                "Системный" if record.system else "Проектный",
                record.code,
                record.lithotype_id,
                record.name_ru,
                record.name_en,
                record.category,
                record.color,
                record.pattern_key,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, record.lithotype_id)
                item.setData(Qt.ItemDataRole.UserRole + 1, record.system)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        values = [self.table.item(row, column) for column in range(8)]
        if any(item is None for item in values):
            return
        source, code, lithotype_id, name_ru, name_en, category, color, pattern = (
            cast(QTableWidgetItem, item) for item in values
        )
        self.id_input.setText(lithotype_id.text())
        self.id_input.setReadOnly(source.text() == "Системный")
        self.code_input.setText(code.text())
        self.name_ru_input.setText(name_ru.text())
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
            self.name_en_input,
            self.category_input,
        ):
            field.clear()
        self.pattern_input.setCurrentText("solid")
        self.color_input.setText("#c9a66b")
        self.id_input.setFocus()

    def _values(self) -> tuple[str, str, str, str, str, str, str]:
        return (
            self.id_input.text(),
            self.code_input.text(),
            self.name_ru_input.text(),
            self.name_en_input.text(),
            self.category_input.text(),
            self.color_input.text(),
            self.pattern_input.currentText(),
        )

    def _choose_color(self) -> None:
        initial = QColor(self.color_input.text())
        selected = QColorDialog.getColor(initial, self, "Цвет литотипа")
        if selected.isValid():
            self.color_input.setText(selected.name())

    def _update_preview(self) -> None:
        self.pattern_preview.set_pattern(
            self.color_input.text(), self.pattern_input.currentText()
        )

    def _add(self) -> None:
        self._run(lambda: self.controller.add(*self._values()))

    def _update(self) -> None:
        lithotype_id = self._selected_id()
        if lithotype_id is None:
            QMessageBox.information(self, "Справочник", "Выберите проектную запись")
            return
        _, code, name_ru, name_en, category, color, pattern = self._values()
        self._run(
            lambda: self.controller.update(
                lithotype_id,
                code=code,
                name_ru=name_ru,
                name_en=name_en,
                category=category,
                color=color,
                pattern_key=pattern,
            )
        )

    def _remove(self) -> None:
        lithotype_id = self._selected_id()
        if lithotype_id is None:
            QMessageBox.information(self, "Справочник", "Выберите проектную запись")
            return
        self._run(lambda: self.controller.remove(lithotype_id))

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "Справочник", str(exc))
            return False
        self._refresh()
        return True
