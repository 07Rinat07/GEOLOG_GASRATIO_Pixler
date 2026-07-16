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
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("masterlog-symbols-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("masterlog_symbols.depth"),
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
        self.column_input = QComboBox()
        for column in template.columns:
            self.column_input.addItem(column.title, column.column_id)
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
        form.addRow(self._t("masterlog_symbols.depth"), self.depth_input)
        form.addRow(self._t("masterlog_symbols.column"), self.column_input)
        form.addRow(self._t("masterlog_symbols.image"), self.asset_input)
        form.addRow(self._t("masterlog_symbols.width"), self.width_input)
        form.addRow(self._t("masterlog_symbols.height"), self.height_input)
        form.addRow(self._t("masterlog_symbols.label"), self.label_input)
        root.addLayout(form)

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
            depth = QTableWidgetItem(f"{symbol.depth:g}")
            depth.setData(Qt.ItemDataRole.UserRole, symbol.object_id)
            self.table.setItem(row, 0, depth)
            self.table.setItem(row, 1, QTableWidgetItem(columns.get(symbol.column_id, symbol.column_id)))
            asset = assets.get(symbol.asset_ref)
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(asset.original_name if asset is not None else symbol.asset_ref),
            )
            self.table.setItem(row, 3, QTableWidgetItem(symbol.label))
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
        self.depth_input.setValue(symbol.depth)
        self.column_input.setCurrentIndex(self.column_input.findData(symbol.column_id))
        self.asset_input.setCurrentIndex(self.asset_input.findData(symbol.asset_ref))
        self.width_input.setValue(symbol.width_mm)
        self.height_input.setValue(symbol.height_mm)
        self.label_input.setText(symbol.label)

    def _values(self) -> tuple[float, str, str, float, float, str]:
        return (
            self.depth_input.value(),
            str(self.column_input.currentData() or ""),
            str(self.asset_input.currentData() or ""),
            self.width_input.value(),
            self.height_input.value(),
            self.label_input.text(),
        )

    def _add(self) -> None:
        depth, column_id, asset_ref, width, height, label = self._values()
        self._run(
            lambda: self.controller.add(
                self.template_id,
                depth=depth,
                column_id=column_id,
                asset_ref=asset_ref,
                width_mm=width,
                height_mm=height,
                label=label,
            )
        )

    def _update(self) -> None:
        selected = self._selected_id()
        if selected is None:
            self._select_first()
            return
        depth, column_id, asset_ref, width, height, label = self._values()
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

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return False
        self._refresh()
        return True
