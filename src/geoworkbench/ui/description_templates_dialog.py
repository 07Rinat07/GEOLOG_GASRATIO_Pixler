from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.project.description_template_controller import DescriptionTemplateController


class DescriptionTemplatesDialog(QDialog):
    def __init__(
        self, controller: DescriptionTemplateController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Шаблоны описаний пород")
        self.resize(760, 520)
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, 2)
        self.table.setObjectName("description-templates-table")
        self.table.setHorizontalHeaderLabels(["Название", "Текст"])
        self.table.itemSelectionChanged.connect(self._load_selected)
        root.addWidget(self.table)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.text_input = QTextEdit()
        form.addRow("Название", self.name_input)
        form.addRow("Текст", self.text_input)
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

    def _refresh(self) -> None:
        templates = self.controller.available()
        self.table.setRowCount(len(templates))
        for row, (name, text) in enumerate(templates):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()

    def _selected_name(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.text() if item is not None else None

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        name = self.table.item(row, 0) if row >= 0 else None
        text = self.table.item(row, 1) if row >= 0 else None
        if name is not None and text is not None:
            self.name_input.setText(name.text())
            self.text_input.setPlainText(text.text())

    def _add(self) -> None:
        self._run(
            lambda: self.controller.add(
                self.name_input.text(), self.text_input.toPlainText()
            )
        )

    def _update(self) -> None:
        original_name = self._selected_name()
        if original_name is None:
            QMessageBox.information(self, "Шаблоны", "Сначала выберите шаблон")
            return
        self._run(
            lambda: self.controller.update(
                original_name, self.name_input.text(), self.text_input.toPlainText()
            )
        )

    def _remove(self) -> None:
        name = self._selected_name()
        if name is None:
            QMessageBox.information(self, "Шаблоны", "Сначала выберите шаблон")
            return
        self._run(lambda: self.controller.remove(name))

    def _run(self, operation: Callable[[], object]) -> None:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "Шаблоны", str(exc))
            return
        self._refresh()
