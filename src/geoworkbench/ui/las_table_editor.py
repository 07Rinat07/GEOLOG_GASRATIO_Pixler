from __future__ import annotations

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import Dataset
from geoworkbench.project.las_range_editor import LasRangeEditingController, RangeClipboard


class LasTableModel(QAbstractTableModel):
    edit_failed = Signal(str)
    dataset_edited = Signal()

    def __init__(self, controller: LasRangeEditingController) -> None:
        super().__init__()
        self.controller = controller
        self.dataset: Dataset | None = None

    def set_dataset(self, dataset: Dataset | None) -> None:
        self.beginResetModel()
        self.dataset = dataset
        self.endResetModel()

    def rowCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        if parent.isValid() or self.dataset is None:
            return 0
        return int(self.dataset.depth.size)

    def columnCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        if parent.isValid() or self.dataset is None:
            return 0
        return 1 + len(self.dataset.curves)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        if not index.isValid() or self.dataset is None:
            return None
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None
        value = self._value(index.row(), index.column())
        if role == Qt.ItemDataRole.EditRole:
            return "" if not np.isfinite(value) else f"{value:.15g}"
        return "—" if not np.isfinite(value) else f"{value:.8g}"

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]  # noqa: E501, N802
        if role != Qt.ItemDataRole.DisplayRole or self.dataset is None:
            return None
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        if section == 0:
            unit = "ms" if self.dataset.depth_domain.value == "time" else "m"
            return f"DEPTH\n[{unit}]"
        curve = list(self.dataset.curves.values())[section - 1]
        unit = f"\n[{curve.metadata.unit}]" if curve.metadata.unit else ""
        return curve.metadata.original_mnemonic + unit

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # type: ignore[override]
        flags = super().flags(index)
        if not index.isValid() or self.dataset is None or index.column() == 0:
            return flags
        curve = list(self.dataset.curves.values())[index.column() - 1]
        if not curve.metadata.provenance.startswith("calculation:"):
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:  # type: ignore[override]  # noqa: E501, N802
        if role != Qt.ItemDataRole.EditRole or not index.isValid() or self.dataset is None:
            return False
        if index.column() == 0:
            self.edit_failed.emit(
                "Индекс глубины изменяется отдельной операцией с предварительной проверкой"
            )
            return False
        curves_before = len(self.dataset.curves)
        curve = list(self.dataset.curves.values())[index.column() - 1]
        try:
            numeric = float(str(value).strip().replace(",", "."))
            self.controller.edit_cell(curve.metadata.curve_id, index.row(), numeric)
        except (IndexError, KeyError, RuntimeError, ValueError) as exc:
            self.edit_failed.emit(str(exc))
            return False
        if len(self.dataset.curves) != curves_before:
            self.beginResetModel()
            self.endResetModel()
        else:
            left = self.index(index.row(), 0)
            right = self.index(index.row(), self.columnCount() - 1)
            self.dataChanged.emit(left, right)
        self.dataset_edited.emit()
        return True

    def _value(self, row: int, column: int) -> float:
        assert self.dataset is not None
        if column == 0:
            return float(self.dataset.depth[row])
        curve = list(self.dataset.curves.values())[column - 1]
        return float(curve.values[row])


class LasTableEditor(QWidget):
    dataset_edited = Signal()
    edit_failed = Signal(str)

    def __init__(self, controller: LasRangeEditingController) -> None:
        super().__init__()
        self.controller = controller
        self.clipboard: RangeClipboard | None = None
        self.model = LasTableModel(controller)
        self.model.dataset_edited.connect(self.dataset_edited)
        self.model.edit_failed.connect(self.edit_failed)
        self.table = QTableView()
        self.table.setObjectName("las-data-table")
        self.table.setModel(self.model)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.hint = QLabel(
            "Двойной щелчок изменяет исходное значение. Расчётные кривые обновляются автоматически."
        )
        root = QVBoxLayout(self)
        root.addWidget(self.hint)
        actions = QHBoxLayout()
        for label, handler in (
            ("Заполнить значением", self.fill_constant),
            ("Заполнить шумом", self.fill_noise),
            ("Копировать интервал", self.copy_selection),
            ("Вставить", self.paste_selection),
            ("Отменить", self.undo),
            ("Повторить", self.redo),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)
        root.addWidget(self.table)

    def set_dataset(self, dataset: Dataset | None) -> None:
        self.model.set_dataset(dataset)
        self.clipboard = None

    def fill_constant(self) -> None:
        value, accepted = QInputDialog.getDouble(
            self, "Заполнение интервала", "Значение", decimals=8
        )
        if accepted:
            self._run_selection_action(
                lambda curve_ids, top, bottom: self.controller.set_constant(
                    curve_ids, top, bottom, value
                )
            )

    def fill_noise(self) -> None:
        minimum, accepted = QInputDialog.getDouble(
            self, "Случайные значения", "Минимум", 0.5, decimals=8
        )
        if not accepted:
            return
        maximum, accepted = QInputDialog.getDouble(
            self, "Случайные значения", "Максимум", 5.0, decimals=8
        )
        if not accepted:
            return
        seed, accepted = QInputDialog.getInt(self, "Случайные значения", "Seed", 42)
        if accepted:
            self._run_selection_action(
                lambda curve_ids, top, bottom: self.controller.fill_uniform_noise(
                    curve_ids, top, bottom, minimum, maximum, seed=seed
                )
            )

    def copy_selection(self) -> None:
        try:
            curve_ids, top, bottom = self._selected_range()
            self.clipboard = self.controller.copy(curve_ids, top, bottom)
        except (KeyError, RuntimeError, ValueError) as exc:
            self.edit_failed.emit(str(exc))

    def paste_selection(self) -> None:
        if self.clipboard is None:
            self.edit_failed.emit("Сначала скопируйте интервал")
            return
        dataset = self.model.dataset
        rows = {index.row() for index in self.table.selectedIndexes()}
        if dataset is None or not rows:
            self.edit_failed.emit("Выберите начальную строку вставки")
            return
        try:
            self.controller.paste(self.clipboard, float(dataset.depth[min(rows)]))
        except (KeyError, RuntimeError, ValueError) as exc:
            self.edit_failed.emit(str(exc))
            return
        self._refresh_after_operation()

    def undo(self) -> None:
        self._run_history_action(self.controller.undo)

    def redo(self) -> None:
        self._run_history_action(self.controller.redo)

    def _run_selection_action(self, action) -> None:
        try:
            action(*self._selected_range())
        except (KeyError, RuntimeError, ValueError) as exc:
            self.edit_failed.emit(str(exc))
            return
        self._refresh_after_operation()

    def _run_history_action(self, action) -> None:
        try:
            action()
        except RuntimeError as exc:
            self.edit_failed.emit(str(exc))
            return
        self._refresh_after_operation()

    def _selected_range(self) -> tuple[list[str], float, float]:
        dataset = self.model.dataset
        selected = self.table.selectedIndexes()
        if dataset is None:
            raise RuntimeError("Сначала выберите dataset")
        rows = {index.row() for index in selected}
        columns = sorted({index.column() for index in selected if index.column() > 0})
        if not rows or not columns:
            raise ValueError("Выберите значения одной или нескольких кривых")
        if len(rows) != max(rows) - min(rows) + 1:
            raise ValueError("Строки диапазона должны идти подряд")
        curves = list(dataset.curves.values())
        curve_ids = [curves[column - 1].metadata.curve_id for column in columns]
        depths = np.asarray([dataset.depth[row] for row in rows], dtype=np.float64)
        return curve_ids, float(np.min(depths)), float(np.max(depths))

    def _refresh_after_operation(self) -> None:
        self.model.beginResetModel()
        self.model.endResetModel()
        self.dataset_edited.emit()
