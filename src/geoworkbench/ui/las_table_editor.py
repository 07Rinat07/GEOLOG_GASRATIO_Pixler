from __future__ import annotations

import numpy as np
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QLabel, QTableView, QVBoxLayout, QWidget

from geoworkbench.domain.models import Dataset
from geoworkbench.project.las_range_editor import LasRangeEditingController


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
        root.addWidget(self.table)

    def set_dataset(self, dataset: Dataset | None) -> None:
        self.model.set_dataset(dataset)
