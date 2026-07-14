from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
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

from geoworkbench.project.annotation_controller import DepthAnnotationController


class DepthAnnotationsDialog(QDialog):
    def __init__(
        self,
        controller: DepthAnnotationController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Глубинные заметки")
        self.resize(700, 460)
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, 2)
        self.table.setObjectName("depth-annotations-table")
        self.table.setHorizontalHeaderLabels(["Глубина", "Комментарий"])
        self.table.itemSelectionChanged.connect(self._load_selected)
        root.addWidget(self.table)

        form = QFormLayout()
        self.depth_input = QDoubleSpinBox()
        self.depth_input.setRange(-100_000.0, 100_000.0)
        self.depth_input.setDecimals(3)
        self.text_input = QLineEdit()
        form.addRow("Глубина", self.depth_input)
        form.addRow("Комментарий", self.text_input)
        root.addLayout(form)

        actions = QHBoxLayout()
        add_button = QPushButton("Добавить")
        update_button = QPushButton("Изменить")
        remove_button = QPushButton("Удалить")
        add_button.clicked.connect(self._add)
        update_button.clicked.connect(self._update)
        remove_button.clicked.connect(self._remove)
        actions.addWidget(add_button)
        actions.addWidget(update_button)
        actions.addWidget(remove_button)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        annotations = self.controller.available()
        self.table.setRowCount(len(annotations))
        for row, annotation in enumerate(annotations):
            depth_item = QTableWidgetItem(f"{annotation.depth:g}")
            depth_item.setData(256, annotation.annotation_id)
            self.table.setItem(row, 0, depth_item)
            self.table.setItem(row, 1, QTableWidgetItem(annotation.text))
        self.table.resizeColumnsToContents()

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        depth_item = self.table.item(row, 0) if row >= 0 else None
        if depth_item is None:
            return None
        return str(depth_item.data(256))

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        depth_item = self.table.item(row, 0)
        text_item = self.table.item(row, 1)
        if depth_item is None or text_item is None:
            return
        self.depth_input.setValue(float(depth_item.text()))
        self.text_input.setText(text_item.text())

    def _add(self) -> None:
        if self._run(lambda: self.controller.add(self.depth_input.value(), self.text_input.text())):
            self.text_input.clear()

    def _update(self) -> None:
        annotation_id = self._selected_id()
        if annotation_id is None:
            QMessageBox.information(self, "Заметки", "Сначала выберите заметку")
            return
        self._run(
            lambda: self.controller.update(
                annotation_id,
                depth=self.depth_input.value(),
                text=self.text_input.text(),
            )
        )

    def _remove(self) -> None:
        annotation_id = self._selected_id()
        if annotation_id is None:
            QMessageBox.information(self, "Заметки", "Сначала выберите заметку")
            return
        self._run(lambda: self.controller.remove(annotation_id))

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Заметки", str(exc))
            return False
        self._refresh()
        return True
