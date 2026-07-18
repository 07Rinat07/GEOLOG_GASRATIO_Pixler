from __future__ import annotations

import numpy as np
from PySide6.QtCore import (
    QAbstractTableModel,
    QItemSelection,
    QItemSelectionModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.data.number_format import (
    NumberDisplayFormat,
    NumberFormatMode,
    format_decimal_number,
    format_display_number,
)
from geoworkbench.domain.models import Dataset
from geoworkbench.project.las_range_editor import LasRangeEditingController, RangeClipboard
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.dataset_selection import DatasetIntervalSelection


class LasTableModel(QAbstractTableModel):
    edit_failed = Signal(str)
    dataset_edited = Signal()

    def __init__(self, controller: LasRangeEditingController, localizer: Localizer) -> None:
        super().__init__()
        self.controller = controller
        self.localizer = localizer
        self.dataset: Dataset | None = None
        self._number_formats: dict[str, NumberDisplayFormat] = {}

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
            return "" if not np.isfinite(value) else format_decimal_number(value)
        return (
            "—"
            if not np.isfinite(value)
            else format_display_number(value, self.number_format_for_column(index.column()))
        )

    def set_number_formats(self, formats: dict[str, NumberDisplayFormat]) -> None:
        if not all(
            isinstance(key, str)
            and bool(key)
            and isinstance(value, NumberDisplayFormat)
            for key, value in formats.items()
        ):
            raise TypeError("Настройки числовых колонок имеют неверный формат")
        self.beginResetModel()
        self._number_formats = dict(formats)
        self.endResetModel()

    def number_formats(self) -> dict[str, NumberDisplayFormat]:
        return dict(self._number_formats)

    def number_format_for_column(self, column: int) -> NumberDisplayFormat:
        return self._number_formats.get(self._number_format_key(column), NumberDisplayFormat())

    def apply_number_format(
        self, columns: list[int], settings: NumberDisplayFormat
    ) -> None:
        if self.dataset is None:
            raise RuntimeError(self.localizer.text("table.select_dataset"))
        if not columns or any(column < 0 or column >= self.columnCount() for column in columns):
            raise ValueError(self.localizer.text("table.number_format.select_columns"))
        self.beginResetModel()
        for column in columns:
            self._number_formats[self._number_format_key(column)] = settings
        self.endResetModel()

    def _number_format_key(self, column: int) -> str:
        if self.dataset is None or column < 0 or column >= self.columnCount():
            raise IndexError(column)
        if column == 0:
            return f"index:{self.dataset.active_index.mnemonic.casefold()}"
        curve = list(self.dataset.curves.values())[column - 1]
        mnemonic = curve.metadata.canonical_mnemonic or curve.metadata.original_mnemonic
        return f"curve:{mnemonic.casefold()}"

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
                self.localizer.text("table.depth_readonly")
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


class NumberFormatDialog(QDialog):
    def __init__(
        self,
        column_names: list[str],
        settings: NumberDisplayFormat,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self.localizer.text("table.number_format.title"))
        self.columns_label = QLabel(", ".join(column_names))
        self.columns_label.setWordWrap(True)
        self.mode_input = QComboBox()
        for mode in NumberFormatMode:
            self.mode_input.addItem(
                self.localizer.text(f"table.number_format.mode.{mode.value}"), mode
            )
        self.mode_input.setCurrentIndex(self.mode_input.findData(settings.mode))
        self.precision_input = QSpinBox()
        self.precision_input.setRange(0, 15)
        self.precision_input.setValue(settings.precision)
        self.preview_label = QLabel()
        layout = QFormLayout(self)
        layout.addRow(self.localizer.text("table.number_format.columns"), self.columns_label)
        layout.addRow(self.localizer.text("table.number_format.mode"), self.mode_input)
        layout.addRow(
            self.localizer.text("table.number_format.precision"), self.precision_input
        )
        layout.addRow(self.localizer.text("table.number_format.preview"), self.preview_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.mode_input.currentIndexChanged.connect(self._update_preview)
        self.precision_input.valueChanged.connect(self._update_preview)
        self._update_preview()

    def value(self) -> NumberDisplayFormat:
        try:
            mode = NumberFormatMode(str(self.mode_input.currentData()))
        except ValueError:
            mode = NumberFormatMode.ADAPTIVE
        return NumberDisplayFormat(mode, self.precision_input.value())

    def _update_preview(self) -> None:
        adaptive = str(self.mode_input.currentData()) == NumberFormatMode.ADAPTIVE.value
        self.precision_input.setMinimum(1 if adaptive else 0)
        self.preview_label.setText(format_display_number(5.2e-5, self.value()))


class LasTableEditor(QWidget):
    dataset_edited = Signal()
    edit_failed = Signal(str)
    number_formats_changed = Signal(object)

    def __init__(
        self,
        controller: LasRangeEditingController,
        *,
        language: AppLanguage = AppLanguage.RU,
        selection: DatasetIntervalSelection | None = None,
        number_formats: dict[str, NumberDisplayFormat] | None = None,
    ) -> None:
        super().__init__()
        self.localizer = Localizer.create(language)
        self.controller = controller
        self.selection = selection or DatasetIntervalSelection()
        self._applying_shared_selection = False
        self.clipboard: RangeClipboard | None = None
        self.model = LasTableModel(controller, self.localizer)
        self.model.set_number_formats(number_formats or {})
        self.model.dataset_edited.connect(self.dataset_edited)
        self.model.edit_failed.connect(self.edit_failed)
        self.table = QTableView()
        self.table.setObjectName("las-data-table")
        self.table.setModel(self.model)
        self.table.selectionModel().selectionChanged.connect(self._publish_selection)
        self.selection.changed.connect(self._apply_shared_selection)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.hint = QLabel(self._t("table.hint"))
        root = QVBoxLayout(self)
        root.addWidget(self.hint)
        actions = QHBoxLayout()
        for label, handler in (
            (self._t("table.fill_constant"), self.fill_constant),
            (self._t("table.set_missing"), self.set_missing),
            (self._t("table.interpolate"), self.interpolate_missing),
            (self._t("table.fill_noise"), self.fill_noise),
            (self._t("table.copy_interval"), self.copy_selection),
            (self._t("table.paste"), self.paste_selection),
            (self._t("common.undo"), self.undo),
            (self._t("common.redo"), self.redo),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            actions.addWidget(button)
        self.number_format_button = QPushButton(self._t("table.number_format.action"))
        self.number_format_button.clicked.connect(self.configure_number_format)
        actions.addWidget(self.number_format_button)
        actions.addStretch()
        root.addLayout(actions)
        root.addWidget(self.table)
        self._create_context_actions()

    def _t(self, key: str) -> str:
        return self.localizer.text(key)

    def set_dataset(self, dataset: Dataset | None) -> None:
        self.model.set_dataset(dataset)
        self.clipboard = None
        if dataset is None or self.selection.dataset_id != dataset.dataset_id:
            self.selection.clear()
        else:
            self._apply_shared_selection()

    def set_number_formats(self, formats: dict[str, NumberDisplayFormat]) -> None:
        self.model.set_number_formats(formats)

    def configure_number_format(self) -> None:
        columns = sorted({index.column() for index in self.table.selectedIndexes()})
        current = self.table.currentIndex()
        if not columns and current.isValid():
            columns = [current.column()]
        if self.model.dataset is None or not columns:
            self.edit_failed.emit(self._t("table.number_format.select_columns"))
            return
        names = [
            str(self.model.headerData(column, Qt.Orientation.Horizontal)).replace("\n", " ")
            for column in columns
        ]
        dialog = NumberFormatDialog(
            names,
            self.model.number_format_for_column(columns[0]),
            self,
            language=self.localizer.language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.model.apply_number_format(columns, dialog.value())
        self.number_formats_changed.emit(self.model.number_formats())

    def _publish_selection(self) -> None:
        if self._applying_shared_selection:
            return
        dataset = self.model.dataset
        selected = self.table.selectedIndexes()
        if dataset is None or not selected:
            return
        rows = {index.row() for index in selected}
        columns = sorted({index.column() for index in selected if index.column() > 0})
        curves = list(dataset.curves.values())
        curve_ids = tuple(curves[column - 1].metadata.curve_id for column in columns)
        depths = dataset.depth[np.asarray(sorted(rows), dtype=np.int64)]
        try:
            self.selection.select(
                dataset, float(np.min(depths)), float(np.max(depths)), curve_ids
            )
        except (KeyError, ValueError):
            return

    def _apply_shared_selection(self) -> None:
        dataset = self.model.dataset
        interval = self.selection.interval
        if (
            dataset is None
            or interval is None
            or self.selection.dataset_id != dataset.dataset_id
        ):
            return
        indices = np.flatnonzero(
            np.isfinite(dataset.depth)
            & (dataset.depth >= interval[0])
            & (dataset.depth <= interval[1])
        )
        if indices.size == 0 or self.model.columnCount() == 0:
            return
        curve_columns = {
            curve.metadata.curve_id: column
            for column, curve in enumerate(dataset.curves.values(), start=1)
        }
        columns = [
            curve_columns[curve_id]
            for curve_id in self.selection.curve_ids
            if curve_id in curve_columns
        ] or [0]
        selection = QItemSelection()
        for column in columns:
            selection.select(
                self.model.index(int(indices[0]), column),
                self.model.index(int(indices[-1]), column),
            )
        self._applying_shared_selection = True
        try:
            self.table.selectionModel().select(
                selection,
                QItemSelectionModel.SelectionFlag.ClearAndSelect,
            )
            self.table.scrollTo(self.model.index(int(indices[0]), columns[0]))
        finally:
            self._applying_shared_selection = False

    def fill_constant(self) -> None:
        value, accepted = QInputDialog.getDouble(
            self, self._t("table.fill_title"), self._t("table.value"), decimals=8
        )
        if accepted:
            self._run_selection_action(
                lambda curve_ids, top, bottom: self.controller.set_constant(
                    curve_ids, top, bottom, value
                )
            )

    def fill_noise(self) -> None:
        minimum, accepted = QInputDialog.getDouble(
            self, self._t("table.noise_title"), self._t("table.minimum"), 0.5, decimals=8
        )
        if not accepted:
            return
        maximum, accepted = QInputDialog.getDouble(
            self, self._t("table.noise_title"), self._t("table.maximum"), 5.0, decimals=8
        )
        if not accepted:
            return
        seed, accepted = QInputDialog.getInt(
            self, self._t("table.noise_title"), self._t("table.seed"), 42
        )
        if accepted:
            self._run_selection_action(
                lambda curve_ids, top, bottom: self.controller.fill_uniform_noise(
                    curve_ids, top, bottom, minimum, maximum, seed=seed
                )
            )

    def shift_values(self) -> None:
        offset, accepted = QInputDialog.getDouble(
            self,
            self._t("table.shift_title"),
            self._t("table.offset"),
            decimals=8,
        )
        if accepted:
            self._run_selection_action(
                lambda curve_ids, top, bottom: self.controller.add_constant(
                    curve_ids, top, bottom, offset
                )
            )

    def multiply_values(self) -> None:
        factor, accepted = QInputDialog.getDouble(
            self,
            self._t("table.multiply_title"),
            self._t("table.factor"),
            1.0,
            decimals=8,
        )
        if accepted:
            self._run_selection_action(
                lambda curve_ids, top, bottom: self.controller.multiply(
                    curve_ids, top, bottom, factor
                )
            )

    def smooth_values(self) -> None:
        window, accepted = QInputDialog.getInt(
            self,
            self._t("table.smooth_title"),
            self._t("table.window"),
            3,
            3,
            999,
            2,
        )
        if accepted:
            self._run_selection_action(
                lambda curve_ids, top, bottom: self.controller.smooth_moving_average(
                    curve_ids, top, bottom, window
                )
            )

    def set_missing(self) -> None:
        self._run_selection_action(self.controller.set_missing)

    def interpolate_missing(self) -> None:
        self._run_selection_action(self.controller.interpolate_missing)

    def copy_selection(self) -> None:
        try:
            curve_ids, top, bottom = self._selected_range()
            self.clipboard = self.controller.copy(curve_ids, top, bottom)
        except (KeyError, RuntimeError, ValueError) as exc:
            self.edit_failed.emit(str(exc))

    def paste_selection(self) -> None:
        if self.clipboard is None:
            self.edit_failed.emit(self._t("table.copy_first"))
            return
        dataset = self.model.dataset
        rows = {index.row() for index in self.table.selectedIndexes()}
        if dataset is None or not rows:
            self.edit_failed.emit(self._t("table.select_paste_row"))
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
            raise RuntimeError(self._t("table.select_dataset"))
        rows = {index.row() for index in selected}
        columns = sorted({index.column() for index in selected if index.column() > 0})
        if not rows or not columns:
            raise ValueError(self._t("table.select_curves"))
        if len(rows) != max(rows) - min(rows) + 1:
            raise ValueError(self._t("table.contiguous_rows"))
        curves = list(dataset.curves.values())
        curve_ids = [curves[column - 1].metadata.curve_id for column in columns]
        depths = np.asarray([dataset.depth[row] for row in rows], dtype=np.float64)
        return curve_ids, float(np.min(depths)), float(np.max(depths))

    def _refresh_after_operation(self) -> None:
        self.model.beginResetModel()
        self.model.endResetModel()
        self.dataset_edited.emit()

    def _create_context_actions(self) -> None:
        self.shift_action = QAction(self._t("table.shift"), self)
        self.shift_action.triggered.connect(self.shift_values)
        self.multiply_action = QAction(self._t("table.multiply"), self)
        self.multiply_action.triggered.connect(self.multiply_values)
        self.smooth_action = QAction(self._t("table.smooth"), self)
        self.smooth_action.triggered.connect(self.smooth_values)

    def _show_context_menu(self, position) -> None:
        menu = QMenu(self)
        menu.addAction(self.shift_action)
        menu.addAction(self.multiply_action)
        menu.addAction(self.smooth_action)
        menu.exec(self.table.viewport().mapToGlobal(position))
