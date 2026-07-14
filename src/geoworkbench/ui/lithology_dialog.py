from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QDoubleSpinBox,
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

from geoworkbench.catalogs.lithotypes import load_lithotype_catalog
from geoworkbench.project.lithology_controller import LithologyController
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype


class LithologyDialog(QDialog):
    def __init__(
        self,
        controller: LithologyController,
        parent: QWidget | None = None,
        *,
        catalog: tuple[CatalogLithotype, ...] | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.catalog = catalog if catalog is not None else load_lithotype_catalog()
        self.setWindowTitle("Литологические интервалы")
        self.resize(820, 520)
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("lithology-intervals-table")
        self.table.setHorizontalHeaderLabels(["Кровля", "Подошва", "Литотип", "Описание"])
        self.table.itemSelectionChanged.connect(self._load_selected)
        root.addWidget(self.table)

        form = QFormLayout()
        self.top_input = self._depth_input()
        self.bottom_input = self._depth_input()
        self.lithotype_input = QComboBox()
        self.lithotype_input.setEditable(True)
        for item in self.catalog:
            self.lithotype_input.addItem(f"{item.name_ru} ({item.lithotype_id})", item.lithotype_id)
        self.description_input = QLineEdit()
        form.addRow("Кровля", self.top_input)
        form.addRow("Подошва", self.bottom_input)
        form.addRow("ID литотипа", self.lithotype_input)
        form.addRow("Описание", self.description_input)
        root.addLayout(form)

        actions = QHBoxLayout()
        for title, handler in (
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

    @staticmethod
    def _depth_input() -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(-100_000.0, 100_000.0)
        field.setDecimals(3)
        return field

    def _refresh(self) -> None:
        intervals = self.controller.available()
        self.table.setRowCount(len(intervals))
        for row, interval in enumerate(intervals):
            top_item = QTableWidgetItem(f"{interval.top_depth:g}")
            top_item.setData(256, interval.interval_id)
            self.table.setItem(row, 0, top_item)
            self.table.setItem(row, 1, QTableWidgetItem(f"{interval.bottom_depth:g}"))
            self.table.setItem(row, 2, QTableWidgetItem(interval.lithotype_id))
            self.table.setItem(row, 3, QTableWidgetItem(interval.description or ""))
        self.table.resizeColumnsToContents()

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(256)) if item is not None else None

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        items = [self.table.item(row, column) for column in range(4)] if row >= 0 else []
        if len(items) != 4 or any(item is None for item in items):
            return
        top_item, bottom_item, lithotype_item, description_item = items
        assert top_item is not None
        assert bottom_item is not None
        assert lithotype_item is not None
        assert description_item is not None
        self.top_input.setValue(float(top_item.text()))
        self.bottom_input.setValue(float(bottom_item.text()))
        index = self.lithotype_input.findData(lithotype_item.text())
        if index >= 0:
            self.lithotype_input.setCurrentIndex(index)
        else:
            self.lithotype_input.setEditText(lithotype_item.text())
        self.description_input.setText(description_item.text())

    def _add(self) -> None:
        if self._run(
            lambda: self.controller.add(
                self.top_input.value(),
                self.bottom_input.value(),
                self._lithotype_id(),
                description=self.description_input.text(),
            )
        ):
            self.description_input.clear()

    def _update(self) -> None:
        interval_id = self._selected_id()
        if interval_id is None:
            QMessageBox.information(self, "Литология", "Сначала выберите интервал")
            return
        self._run(
            lambda: self.controller.update(
                interval_id,
                top_depth=self.top_input.value(),
                bottom_depth=self.bottom_input.value(),
                lithotype_id=self._lithotype_id(),
                description=self.description_input.text(),
            )
        )

    def _remove(self) -> None:
        interval_id = self._selected_id()
        if interval_id is None:
            QMessageBox.information(self, "Литология", "Сначала выберите интервал")
            return
        self._run(lambda: self.controller.remove(interval_id))

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Литология", str(exc))
            return False
        self._refresh()
        return True

    def _lithotype_id(self) -> str:
        data = self.lithotype_input.currentData()
        return str(data) if data is not None else self.lithotype_input.currentText().strip()
