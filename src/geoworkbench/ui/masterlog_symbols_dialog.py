from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from geoworkbench.project.masterlog_symbol_controller import MasterlogSymbolController
from geoworkbench.services.localization import AppLanguage, Localizer


class MasterlogSymbolsDialog(QDialog):
    def __init__(
        self,
        controller: MasterlogSymbolController,
        template_id: str,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.template_id = template_id
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("masterlog_symbols.title"))
        self.resize(760, 480)
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setObjectName("masterlog-symbols-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("masterlog_symbols.depth"),
                self._t("masterlog_symbols.anchor"),
                self._t("masterlog_symbols.column"),
                self._t("masterlog_symbols.image"),
                self._t("masterlog_symbols.label"),
            ]
        )
        self.table.itemSelectionChanged.connect(self._load_selected)
        root.addWidget(self.table)

        template = controller.session.project.masterlog_templates[template_id]
        form = QFormLayout()
        self.depth_input = QDoubleSpinBox()
        self.depth_input.setRange(-100_000.0, 100_000.0)
        self.depth_input.setDecimals(3)
        self.anchor_input = QComboBox()
        self.anchor_input.addItem(self._t("masterlog_symbols.point"), "depth")
        self.anchor_input.addItem(self._t("masterlog_symbols.interval"), "interval")
        self.anchor_input.addItem(self._t("masterlog_symbols.parameter"), "parameter")
        self.anchor_input.addItem(self._t("masterlog_symbols.time"), "time")
        self.bottom_depth_input = QDoubleSpinBox()
        self.bottom_depth_input.setRange(-100_000.0, 100_000.0)
        self.bottom_depth_input.setDecimals(3)
        self.column_input = QComboBox()
        for column in template.columns:
            self.column_input.addItem(column.title, column.column_id)
        self.parameter_input = QComboBox()
        self.time_input = QLineEdit()
        self.asset_input = QComboBox()
        for asset in sorted(
            controller.session.image_assets.values(),
            key=lambda item: item.original_name.casefold(),
        ):
            self.asset_input.addItem(asset.original_name, asset.asset_id)
        self.width_input = QDoubleSpinBox()
        self.height_input = QDoubleSpinBox()
        for control in (self.width_input, self.height_input):
            control.setRange(1.0, 50.0)
            control.setValue(8.0)
            control.setSuffix(" mm")
        self.label_input = QLineEdit()
        self.label_input.setMaxLength(200)
        form.addRow(self._t("masterlog_symbols.anchor"), self.anchor_input)
        self.depth_label = QLabel(self._t("masterlog_symbols.depth"))
        form.addRow(self.depth_label, self.depth_input)
        self.bottom_depth_label = QLabel(self._t("masterlog_symbols.bottom_depth"))
        form.addRow(self.bottom_depth_label, self.bottom_depth_input)
        form.addRow(self._t("masterlog_symbols.column"), self.column_input)
        self.parameter_label = QLabel(self._t("masterlog_symbols.parameter"))
        form.addRow(self.parameter_label, self.parameter_input)
        self.time_label = QLabel(self._t("masterlog_symbols.time_value"))
        form.addRow(self.time_label, self.time_input)
        form.addRow(self._t("masterlog_symbols.image"), self.asset_input)
        form.addRow(self._t("masterlog_symbols.width"), self.width_input)
        form.addRow(self._t("masterlog_symbols.height"), self.height_input)
        form.addRow(self._t("masterlog_symbols.label"), self.label_input)
        root.addLayout(form)
        self.anchor_input.currentIndexChanged.connect(self._update_anchor_inputs)
        self.column_input.currentIndexChanged.connect(self._refresh_parameter_input)
        self._refresh_parameter_input()
        self._update_anchor_inputs()

        actions = QHBoxLayout()
        add_button = QPushButton(self._t("common.add"))
        update_button = QPushButton(self._t("common.update"))
        remove_button = QPushButton(self._t("common.remove"))
        self.undo_button = QPushButton(self._t("common.undo"))
        self.redo_button = QPushButton(self._t("common.redo"))
        add_button.clicked.connect(self._add)
        update_button.clicked.connect(self._update)
        remove_button.clicked.connect(self._remove)
        self.undo_button.clicked.connect(self._undo)
        self.redo_button.clicked.connect(self._redo)
        for button in (add_button, update_button, remove_button, self.undo_button, self.redo_button):
            actions.addWidget(button)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    def _refresh(self) -> None:
        symbols = self.controller.available(self.template_id)
        self.table.setRowCount(len(symbols))
        template = self.controller.session.project.masterlog_templates[self.template_id]
        columns = {item.column_id: item.title for item in template.columns}
        assets = self.controller.session.image_assets
        for row, symbol in enumerate(symbols):
            depth_text = (
                f"{symbol.top_depth:g}–{symbol.bottom_depth:g}"
                if symbol.anchor_type == "interval"
                else f"{symbol.top_depth:g}"
            )
            depth = QTableWidgetItem(depth_text)
            depth.setData(Qt.ItemDataRole.UserRole, symbol.object_id)
            self.table.setItem(row, 0, depth)
            self.table.setItem(
                row,
                1,
                QTableWidgetItem(self._t(f"masterlog_symbols.{symbol.anchor_type}")),
            )
            self.table.setItem(row, 2, QTableWidgetItem(columns.get(symbol.column_id, symbol.column_id)))
            asset = assets.get(symbol.asset_ref)
            self.table.setItem(
                row,
                3,
                QTableWidgetItem(asset.original_name if asset is not None else symbol.asset_ref),
            )
            self.table.setItem(row, 4, QTableWidgetItem(symbol.label))
        self.table.resizeColumnsToContents()
        self.undo_button.setEnabled(self.controller.history.can_undo)
        self.redo_button.setEnabled(self.controller.history.can_redo)

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _load_selected(self) -> None:
        selected = self._selected_id()
        if selected is None:
            return
        symbol = next(item for item in self.controller.available(self.template_id) if item.object_id == selected)
        self.anchor_input.setCurrentIndex(self.anchor_input.findData(symbol.anchor_type))
        self.depth_input.setValue(symbol.top_depth)
        self.bottom_depth_input.setValue(symbol.bottom_depth)
        self.column_input.setCurrentIndex(self.column_input.findData(symbol.column_id))
        self.parameter_input.setCurrentIndex(
            self.parameter_input.findData(symbol.parameter_mnemonic)
        )
        self.time_input.setText(symbol.time_value or "")
        self.asset_input.setCurrentIndex(self.asset_input.findData(symbol.asset_ref))
        self.width_input.setValue(symbol.width_mm)
        self.height_input.setValue(symbol.height_mm)
        self.label_input.setText(symbol.label)

    def _values(
        self,
    ) -> tuple[
        str, float, float | None, str, str, float, float, str, str | None, str | None
    ]:
        return (
            str(self.anchor_input.currentData() or "depth"),
            self.depth_input.value(),
            self.bottom_depth_input.value()
            if self.anchor_input.currentData() == "interval"
            else None,
            str(self.column_input.currentData() or ""),
            str(self.asset_input.currentData() or ""),
            self.width_input.value(),
            self.height_input.value(),
            self.label_input.text(),
            str(self.parameter_input.currentData() or "")
            if self.anchor_input.currentData() == "parameter"
            else None,
            self.time_input.text() if self.anchor_input.currentData() == "time" else None,
        )

    def _add(self) -> None:
        (
            anchor, depth, bottom, column_id, asset_ref, width, height, label, parameter, time_value
        ) = self._values()
        self._run(
            lambda: self.controller.add(
                self.template_id,
                depth=depth,
                column_id=column_id,
                asset_ref=asset_ref,
                width_mm=width,
                height_mm=height,
                label=label,
                anchor_type=anchor,
                bottom_depth=bottom,
                parameter_mnemonic=parameter,
                time_value=time_value,
            )
        )

    def _update(self) -> None:
        selected = self._selected_id()
        if selected is None:
            self._select_first()
            return
        (
            anchor, depth, bottom, column_id, asset_ref, width, height, label, parameter, time_value
        ) = self._values()
        self._run(
            lambda: self.controller.update(
                selected,
                template_id=self.template_id,
                depth=depth,
                column_id=column_id,
                asset_ref=asset_ref,
                width_mm=width,
                height_mm=height,
                label=label,
                anchor_type=anchor,
                bottom_depth=bottom,
                parameter_mnemonic=parameter,
                time_value=time_value,
            )
        )

    def _remove(self) -> None:
        selected = self._selected_id()
        if selected is None:
            self._select_first()
            return
        self._run(lambda: self.controller.remove(selected, self.template_id))

    def _undo(self) -> None:
        self._run(self.controller.undo)

    def _redo(self) -> None:
        self._run(self.controller.redo)

    def _select_first(self) -> None:
        QMessageBox.information(
            self, self.windowTitle(), self._t("masterlog_symbols.select_first")
        )

    def _update_anchor_inputs(self) -> None:
        interval = self.anchor_input.currentData() == "interval"
        parameter = self.anchor_input.currentData() == "parameter"
        time_anchor = self.anchor_input.currentData() == "time"
        self.bottom_depth_label.setVisible(interval)
        self.bottom_depth_input.setVisible(interval)
        self.height_input.setEnabled(not interval)
        self.parameter_label.setVisible(parameter)
        self.parameter_input.setVisible(parameter)
        self.time_label.setVisible(time_anchor)
        self.time_input.setVisible(time_anchor)
        self.depth_label.setVisible(not time_anchor)
        self.depth_input.setVisible(not time_anchor)

    def _refresh_parameter_input(self) -> None:
        selected = self.parameter_input.currentData()
        self.parameter_input.clear()
        template = self.controller.session.project.masterlog_templates[self.template_id]
        column_id = self.column_input.currentData()
        column = next((item for item in template.columns if item.column_id == column_id), None)
        if column is not None:
            for mnemonic in column.curve_mnemonics:
                self.parameter_input.addItem(mnemonic, mnemonic)
        index = self.parameter_input.findData(selected)
        if index >= 0:
            self.parameter_input.setCurrentIndex(index)

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return False
        self._refresh()
        return True
