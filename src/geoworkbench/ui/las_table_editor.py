from __future__ import annotations

from enum import StrEnum

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
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QMenu,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.data.selection_export import (
    SelectionExportError,
    export_selection_excel,
    export_selection_text,
)
from geoworkbench.data.number_format import (
    NumberDisplayFormat,
    NumberFormatMode,
    format_decimal_number,
    format_display_number,
)
from geoworkbench.domain.models import CurveData, Dataset
from geoworkbench.project.las_range_editor import LasRangeEditingController, RangeClipboard
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.dataset_selection import DatasetIntervalSelection
from geoworkbench.services.las_parameter_resolver import LasParameterResolver, ParameterMatch
from geoworkbench.services.parameter_labels import localized_curve_name


class TableHeaderMode(StrEnum):
    FRIENDLY_TECHNICAL = "friendly_technical"
    FRIENDLY = "friendly"
    TECHNICAL = "technical"


class LasTableModel(QAbstractTableModel):
    edit_failed = Signal(str)
    dataset_edited = Signal()

    def __init__(self, controller: LasRangeEditingController, localizer: Localizer) -> None:
        super().__init__()
        self.controller = controller
        self.localizer = localizer
        self.dataset: Dataset | None = None
        self._number_formats: dict[str, NumberDisplayFormat] = {}
        self._header_mode = TableHeaderMode.FRIENDLY_TECHNICAL
        self._resolver = LasParameterResolver()
        self._parameter_matches: dict[str, ParameterMatch] = {}

    def set_dataset(self, dataset: Dataset | None) -> None:
        self.beginResetModel()
        self.dataset = dataset
        self._rebuild_parameter_matches()
        self.endResetModel()

    @property
    def header_mode(self) -> TableHeaderMode:
        return self._header_mode

    def set_header_mode(self, mode: TableHeaderMode | str) -> None:
        resolved = TableHeaderMode(mode)
        if resolved is self._header_mode:
            return
        self._header_mode = resolved
        if self.columnCount() > 0:
            self.headerDataChanged.emit(
                Qt.Orientation.Horizontal,
                0,
                self.columnCount() - 1,
            )

    def refresh_parameter_labels(self) -> None:
        self._rebuild_parameter_matches()
        if self.columnCount() > 0:
            self.headerDataChanged.emit(
                Qt.Orientation.Horizontal,
                0,
                self.columnCount() - 1,
            )

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
            isinstance(key, str) and bool(key) and isinstance(value, NumberDisplayFormat)
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

    def apply_number_format(self, columns: list[int], settings: NumberDisplayFormat) -> None:
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

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ):  # type: ignore[override]  # noqa: E501, N802
        if self.dataset is None:
            return None
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1) if role == Qt.ItemDataRole.DisplayRole else None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        if section == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                return self._index_header_text()
            if role == Qt.ItemDataRole.ToolTipRole:
                return self._index_tooltip()
            if role == Qt.ItemDataRole.AccessibleTextRole:
                return self._index_friendly_name()
            return None
        curve = list(self.dataset.curves.values())[section - 1]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._curve_header_text(curve)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._curve_tooltip(curve)
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return self._curve_friendly_name(curve)
        return None

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
            self.edit_failed.emit(self.localizer.text("table.depth_readonly"))
            return False
        curves_before = len(self.dataset.curves)
        curve = list(self.dataset.curves.values())[index.column() - 1]
        try:
            rendered = str(value).strip()
            numeric = np.nan if rendered == "" else float(rendered.replace(",", "."))
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

    def _rebuild_parameter_matches(self) -> None:
        self._parameter_matches = {}
        if self.dataset is None:
            return
        for curve in self.dataset.curves.values():
            matches = self._resolver.infer_curve(curve)
            if matches:
                self._parameter_matches[curve.metadata.curve_id] = matches[0]

    def _match_for_curve(self, curve: CurveData) -> ParameterMatch | None:
        return self._parameter_matches.get(curve.metadata.curve_id)

    def _recognized_canonical_mnemonic(self, curve: CurveData) -> str:
        match = self._match_for_curve(curve)
        if match is not None:
            return match.canonical_mnemonic
        metadata = curve.metadata
        canonical = (metadata.canonical_mnemonic or "").strip().upper()
        original = metadata.original_mnemonic.strip().upper()
        return canonical if canonical and canonical != original else ""

    def _curve_canonical_mnemonic(self, curve: CurveData) -> str:
        return (
            self._recognized_canonical_mnemonic(curve)
            or curve.metadata.original_mnemonic.strip().upper()
        )

    def _curve_friendly_name(self, curve: CurveData) -> str:
        metadata = curve.metadata
        canonical = self._curve_canonical_mnemonic(curve)
        friendly = localized_curve_name(
            canonical,
            description=metadata.description or "",
            unit=metadata.unit or "",
            language=self.localizer.language,
        ).strip()
        if not friendly:
            friendly = (metadata.description or metadata.original_mnemonic).strip()
        if (
            self._match_for_curve(curve) is None
            and not (metadata.description or "").strip()
            and friendly.casefold() == metadata.original_mnemonic.strip().casefold()
        ):
            friendly = self.localizer.text("table.header.unresolved_name")
        return friendly

    def _curve_technical_name(self, curve: CurveData) -> str:
        original = curve.metadata.original_mnemonic.strip()
        canonical = self._recognized_canonical_mnemonic(curve)
        if not canonical or canonical.casefold() == original.casefold():
            return original
        return f"{original} → {canonical}"

    def _curve_header_text(self, curve: CurveData) -> str:
        unit = f"[{curve.metadata.unit}]" if curve.metadata.unit else "[—]"
        if self._header_mode is TableHeaderMode.TECHNICAL:
            return f"{self._curve_technical_name(curve)}\n{unit}"
        friendly = self._curve_friendly_name(curve)
        if self._header_mode is TableHeaderMode.FRIENDLY:
            return f"{friendly}\n{unit}"
        return f"{friendly}\n{self._curve_technical_name(curve)}\n{unit}"

    def _curve_tooltip(self, curve: CurveData) -> str:
        metadata = curve.metadata
        match = self._match_for_curve(curve)
        canonical = self._recognized_canonical_mnemonic(curve)
        lines = [
            self._curve_friendly_name(curve),
            self.localizer.text(
                "table.header.tooltip.original", value=metadata.original_mnemonic or "—"
            ),
            self.localizer.text("table.header.tooltip.canonical", value=canonical or "—"),
            self.localizer.text(
                "table.header.tooltip.description", value=metadata.description or "—"
            ),
            self.localizer.text("table.header.tooltip.unit", value=metadata.unit or "—"),
        ]
        if match is None:
            lines.append(self.localizer.text("table.header.tooltip.unresolved"))
        else:
            lines.append(
                self.localizer.text(
                    "table.header.tooltip.confidence",
                    value=f"{match.confidence:.0%}",
                )
            )
            lines.append(
                self.localizer.text(
                    "table.header.tooltip.method",
                    value=self._localized_match_method(match.matched_by),
                )
            )
            if match.evidence:
                lines.append(
                    self.localizer.text(
                        "table.header.tooltip.evidence",
                        value="; ".join(match.evidence),
                    )
                )
        if metadata.provenance:
            lines.append(
                self.localizer.text("table.header.tooltip.provenance", value=metadata.provenance)
            )
        return "\n".join(lines)

    def _localized_match_method(self, matched_by: str) -> str:
        key = f"table.header.match_method.{matched_by}"
        translated = self.localizer.text(key)
        return matched_by if translated == key else translated

    def _index_friendly_name(self) -> str:
        assert self.dataset is not None
        return self.localizer.text(f"table.header.index.{self.dataset.depth_domain.value}")

    def _index_technical_name(self) -> str:
        assert self.dataset is not None
        mnemonic = self.dataset.active_index.mnemonic.strip() or "DEPTH"
        return mnemonic

    def _index_unit(self) -> str:
        assert self.dataset is not None
        return (
            self.dataset.active_index.unit
            or ("ms" if self.dataset.depth_domain.value == "time" else "m")
        ).strip()

    def _index_header_text(self) -> str:
        unit = f"[{self._index_unit()}]"
        if self._header_mode is TableHeaderMode.TECHNICAL:
            return f"{self._index_technical_name()}\n{unit}"
        friendly = self._index_friendly_name()
        if self._header_mode is TableHeaderMode.FRIENDLY:
            return f"{friendly}\n{unit}"
        return f"{friendly}\n{self._index_technical_name()}\n{unit}"

    def _index_tooltip(self) -> str:
        assert self.dataset is not None
        evidence = "; ".join(self.dataset.active_index.evidence) or "—"
        return "\n".join(
            (
                self._index_friendly_name(),
                self.localizer.text(
                    "table.header.tooltip.original", value=self._index_technical_name()
                ),
                self.localizer.text("table.header.tooltip.unit", value=self._index_unit() or "—"),
                self.localizer.text(
                    "table.header.tooltip.confidence",
                    value=f"{self.dataset.active_index.confidence:.0%}",
                ),
                self.localizer.text("table.header.tooltip.evidence", value=evidence),
            )
        )


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
        layout.addRow(self.localizer.text("table.number_format.precision"), self.precision_input)
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
        horizontal_header = self.table.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        horizontal_header.setMinimumSectionSize(96)
        horizontal_header.setDefaultSectionSize(150)
        horizontal_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        horizontal_header.setSectionsMovable(True)
        horizontal_header.setToolTip(self._t("table.header.tooltip.hint"))
        horizontal_header.setFixedHeight(78)
        self.hint = QLabel(self._t("table.hint"))
        root = QVBoxLayout(self)
        root.addWidget(self.hint)
        actions = QHBoxLayout()
        self.header_mode_label = QLabel(self._t("table.header.mode.label"))
        self.header_mode_input = QComboBox()
        self._populate_header_modes()
        self.header_mode_input.currentIndexChanged.connect(self._change_header_mode)
        actions.addWidget(self.header_mode_label)
        actions.addWidget(self.header_mode_input)
        self._command_buttons: list[tuple[QPushButton, str]] = []
        for key, handler in (
            ("table.fill_constant", self.fill_constant),
            ("table.set_missing", self.set_missing),
            ("table.interpolate", self.interpolate_missing),
            ("table.fill_noise", self.fill_noise),
            ("table.copy_interval", self.copy_selection),
            ("table.paste", self.paste_selection),
            ("common.undo", self.undo),
            ("common.redo", self.redo),
        ):
            button = QPushButton(self._t(key))
            button.clicked.connect(handler)
            actions.addWidget(button)
            self._command_buttons.append((button, key))
        self.number_format_button = QPushButton(self._t("table.number_format.action"))
        self.number_format_button.clicked.connect(self.configure_number_format)
        actions.addWidget(self.number_format_button)
        self.export_selection_button = QPushButton(self._t("table.export.selection"))
        self.export_selection_button.clicked.connect(self.export_selected_cells)
        actions.addWidget(self.export_selection_button)
        self.export_all_button = QPushButton(self._t("table.export.all"))
        self.export_all_button.clicked.connect(self.export_all_cells)
        actions.addWidget(self.export_all_button)
        actions.addStretch()
        root.addLayout(actions)
        root.addWidget(self.table)
        self._create_context_actions()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def set_language(self, language: AppLanguage) -> None:
        self.localizer = Localizer.create(language)
        self.model.localizer = self.localizer
        self.hint.setText(self._t("table.hint"))
        for button, key in self._command_buttons:
            button.setText(self._t(key))
        self.number_format_button.setText(self._t("table.number_format.action"))
        self.export_selection_button.setText(self._t("table.export.selection"))
        self.export_all_button.setText(self._t("table.export.all"))
        self.header_mode_label.setText(self._t("table.header.mode.label"))
        current_mode = self.model.header_mode
        self._populate_header_modes()
        self.header_mode_input.setCurrentIndex(self.header_mode_input.findData(current_mode))
        self.table.horizontalHeader().setToolTip(self._t("table.header.tooltip.hint"))
        self.copy_cells_action.setText(self._t("table.copy_cells"))
        self.paste_cells_action.setText(self._t("table.paste_cells"))
        self.clear_cells_action.setText(self._t("table.clear_cells"))
        self.shift_action.setText(self._t("table.shift"))
        self.multiply_action.setText(self._t("table.multiply"))
        self.smooth_action.setText(self._t("table.smooth"))
        if self.model.columnCount() > 0:
            self.model.headerDataChanged.emit(
                Qt.Orientation.Horizontal,
                0,
                self.model.columnCount() - 1,
            )

    def set_dataset(self, dataset: Dataset | None) -> None:
        self.model.set_dataset(dataset)
        self._apply_header_geometry()
        self.clipboard = None
        if dataset is None or self.selection.dataset_id != dataset.dataset_id:
            self.selection.clear()
        else:
            self._apply_shared_selection()

    def set_number_formats(self, formats: dict[str, NumberDisplayFormat]) -> None:
        self.model.set_number_formats(formats)

    def _populate_header_modes(self) -> None:
        current = self.model.header_mode
        self.header_mode_input.blockSignals(True)
        try:
            self.header_mode_input.clear()
            for mode in TableHeaderMode:
                self.header_mode_input.addItem(
                    self._t(f"table.header.mode.{mode.value}"),
                    mode,
                )
            self.header_mode_input.setCurrentIndex(self.header_mode_input.findData(current))
        finally:
            self.header_mode_input.blockSignals(False)

    def _change_header_mode(self) -> None:
        mode = self.header_mode_input.currentData()
        if mode is None:
            return
        self.model.set_header_mode(TableHeaderMode(mode))
        self._apply_header_geometry()

    def _apply_header_geometry(self) -> None:
        header = self.table.horizontalHeader()
        if self.model.header_mode is TableHeaderMode.FRIENDLY_TECHNICAL:
            header.setFixedHeight(78)
            minimum_width = 150
            maximum_width = 280
        else:
            header.setFixedHeight(58)
            minimum_width = 130
            maximum_width = 240
        if self.model.columnCount() <= 0:
            return
        metrics = header.fontMetrics()
        for column in range(self.model.columnCount()):
            text = str(self.model.headerData(column, Qt.Orientation.Horizontal) or "")
            content_width = max(
                (metrics.horizontalAdvance(line) for line in text.splitlines()),
                default=minimum_width,
            )
            preferred_width = max(minimum_width, min(maximum_width, content_width + 28))
            if column == 0:
                preferred_width = max(130, min(190, preferred_width))
            self.table.setColumnWidth(column, preferred_width)

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
            self.selection.select(dataset, float(np.min(depths)), float(np.max(depths)), curve_ids)
        except (KeyError, ValueError):
            return

    def _apply_shared_selection(self) -> None:
        dataset = self.model.dataset
        interval = self.selection.interval
        if dataset is None or interval is None or self.selection.dataset_id != dataset.dataset_id:
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

    def copy_cells_to_clipboard(self) -> None:
        selected = self.table.selectedIndexes()
        if not selected:
            self.edit_failed.emit(self._t("table.select_cells"))
            return
        rows = range(min(index.row() for index in selected), max(index.row() for index in selected) + 1)
        columns = range(
            min(index.column() for index in selected),
            max(index.column() for index in selected) + 1,
        )
        selected_coordinates = {(index.row(), index.column()) for index in selected}
        lines: list[str] = []
        for row in rows:
            cells: list[str] = []
            for column in columns:
                if (row, column) not in selected_coordinates:
                    cells.append("")
                    continue
                value = self.model.data(
                    self.model.index(row, column),
                    Qt.ItemDataRole.EditRole,
                )
                cells.append(str(value or ""))
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))

    def paste_cells_from_clipboard(self) -> None:
        dataset = self.model.dataset
        current = self.table.currentIndex()
        if dataset is None:
            self.edit_failed.emit(self._t("table.select_dataset"))
            return
        if not current.isValid():
            self.edit_failed.emit(self._t("table.select_paste_cell"))
            return
        raw = QApplication.clipboard().text()
        if raw == "":
            self.edit_failed.emit(self._t("table.clipboard_empty"))
            return
        rows = [line.split("\t") for line in raw.replace("\r\n", "\n").split("\n")]
        while rows and len(rows[-1]) == 1 and rows[-1][0] == "":
            rows.pop()
        if not rows:
            self.edit_failed.emit(self._t("table.clipboard_empty"))
            return
        width = max(len(row) for row in rows)
        selected = self.table.selectedIndexes()
        if len(rows) == 1 and width == 1 and len(selected) > 1:
            targets = sorted(selected, key=lambda index: (index.column(), index.row()))
            text_values = [rows[0][0]] * len(targets)
        else:
            targets = []
            text_values = []
            for row_offset, values in enumerate(rows):
                for column_offset in range(width):
                    target_row = current.row() + row_offset
                    target_column = current.column() + column_offset
                    if target_row >= self.model.rowCount() or target_column >= self.model.columnCount():
                        self.edit_failed.emit(self._t("table.paste_outside"))
                        return
                    targets.append(self.model.index(target_row, target_column))
                    text_values.append(values[column_offset] if column_offset < len(values) else "")
        if any(index.column() == 0 for index in targets):
            self.edit_failed.emit(self._t("table.depth_readonly"))
            return
        curves = list(dataset.curves.values())
        changes_by_curve: dict[str, list[tuple[int, float]]] = {}
        try:
            for index, text in zip(targets, text_values, strict=True):
                curve = curves[index.column() - 1]
                if curve.metadata.provenance.startswith("calculation:"):
                    raise ValueError(
                        self._t("table.calculated_readonly").format(
                            mnemonic=curve.metadata.original_mnemonic
                        )
                    )
                cleaned = text.strip()
                value = (
                    np.nan
                    if cleaned == ""
                    else float(cleaned.replace(" ", "").replace(",", "."))
                )
                changes_by_curve.setdefault(curve.metadata.curve_id, []).append(
                    (index.row(), value)
                )
            changes = {
                curve_id: (
                    np.asarray([row for row, _ in items], dtype=np.int64),
                    np.asarray([value for _, value in items], dtype=np.float64),
                )
                for curve_id, items in changes_by_curve.items()
            }
            self.controller.edit_matrix(changes)
        except (IndexError, KeyError, RuntimeError, ValueError) as exc:
            self.edit_failed.emit(str(exc))
            return
        self._refresh_after_operation()

    def clear_selected_cells(self) -> None:
        dataset = self.model.dataset
        selected = self.table.selectedIndexes()
        if dataset is None or not selected:
            self.edit_failed.emit(self._t("table.select_cells"))
            return
        curves = list(dataset.curves.values())
        grouped: dict[str, list[int]] = {}
        try:
            for index in selected:
                if index.column() == 0:
                    continue
                curve = curves[index.column() - 1]
                if curve.metadata.provenance.startswith("calculation:"):
                    raise ValueError(
                        self._t("table.calculated_readonly").format(
                            mnemonic=curve.metadata.original_mnemonic
                        )
                    )
                grouped.setdefault(curve.metadata.curve_id, []).append(index.row())
            changes = {
                curve_id: (
                    np.asarray(sorted(set(rows)), dtype=np.int64),
                    np.full(len(set(rows)), np.nan, dtype=np.float64),
                )
                for curve_id, rows in grouped.items()
            }
            self.controller.edit_matrix(changes, description="Очистка выбранных ячеек")
        except (IndexError, KeyError, RuntimeError, ValueError) as exc:
            self.edit_failed.emit(str(exc))
            return
        self._refresh_after_operation()

    def export_selected_cells(self) -> None:
        try:
            curve_ids, top, bottom = self._selected_range()
        except (KeyError, RuntimeError, ValueError) as exc:
            self.edit_failed.emit(str(exc))
            return
        self._export_range(curve_ids, top, bottom, default_stem="las-selection")

    def export_all_cells(self) -> None:
        dataset = self.model.dataset
        if dataset is None:
            self.edit_failed.emit(self._t("table.select_dataset"))
            return
        finite_depth = dataset.depth[np.isfinite(dataset.depth)]
        if finite_depth.size == 0:
            self.edit_failed.emit(self._t("table.no_depth"))
            return
        self._export_range(
            list(dataset.curves),
            float(np.min(finite_depth)),
            float(np.max(finite_depth)),
            default_stem=dataset.name,
        )

    def _export_range(
        self,
        curve_ids: list[str],
        top: float,
        bottom: float,
        *,
        default_stem: str,
    ) -> None:
        dataset = self.model.dataset
        if dataset is None:
            return
        filename, selected_filter = QFileDialog.getSaveFileName(
            self,
            self._t("table.export.title"),
            default_stem,
            "Excel (*.xlsx);;Text TSV (*.txt);;CSV (*.csv)",
        )
        if not filename:
            return
        target = filename
        if selected_filter.startswith("Excel") and not target.casefold().endswith(".xlsx"):
            target += ".xlsx"
        elif selected_filter.startswith("Text") and not target.casefold().endswith(".txt"):
            target += ".txt"
        elif selected_filter.startswith("CSV") and not target.casefold().endswith(".csv"):
            target += ".csv"
        try:
            if target.casefold().endswith(".xlsx"):
                exported = export_selection_excel(
                    dataset, target, curve_ids, top, bottom, overwrite=True
                )
            else:
                delimiter = ";" if target.casefold().endswith(".csv") else "\t"
                exported = export_selection_text(
                    dataset,
                    target,
                    curve_ids,
                    top,
                    bottom,
                    delimiter=delimiter,
                    overwrite=True,
                )
        except (FileExistsError, OSError, SelectionExportError, ValueError) as exc:
            QMessageBox.critical(self, self._t("table.export.title"), str(exc))
            return
        QMessageBox.information(
            self,
            self._t("table.export.title"),
            self._t("table.export.success", name=exported.name),
        )

    def _create_context_actions(self) -> None:
        self.copy_cells_action = QAction(self._t("table.copy_cells"), self)
        self.copy_cells_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_cells_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.copy_cells_action.triggered.connect(self.copy_cells_to_clipboard)
        self.addAction(self.copy_cells_action)
        self.paste_cells_action = QAction(self._t("table.paste_cells"), self)
        self.paste_cells_action.setShortcut(QKeySequence.StandardKey.Paste)
        self.paste_cells_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.paste_cells_action.triggered.connect(self.paste_cells_from_clipboard)
        self.addAction(self.paste_cells_action)
        self.clear_cells_action = QAction(self._t("table.clear_cells"), self)
        self.clear_cells_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.clear_cells_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.clear_cells_action.triggered.connect(self.clear_selected_cells)
        self.addAction(self.clear_cells_action)
        self.shift_action = QAction(self._t("table.shift"), self)
        self.shift_action.triggered.connect(self.shift_values)
        self.multiply_action = QAction(self._t("table.multiply"), self)
        self.multiply_action.triggered.connect(self.multiply_values)
        self.smooth_action = QAction(self._t("table.smooth"), self)
        self.smooth_action.triggered.connect(self.smooth_values)

    def _show_context_menu(self, position) -> None:
        menu = QMenu(self)
        menu.addAction(self.copy_cells_action)
        menu.addAction(self.paste_cells_action)
        menu.addAction(self.clear_cells_action)
        menu.addSeparator()
        menu.addAction(self.shift_action)
        menu.addAction(self.multiply_action)
        menu.addAction(self.smooth_action)
        menu.addSeparator()
        menu.addAction(self._t("table.export.selection"), self.export_selected_cells)
        menu.addAction(self._t("table.export.all"), self.export_all_cells)
        menu.exec(self.table.viewport().mapToGlobal(position))
