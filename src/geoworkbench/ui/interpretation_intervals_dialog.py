from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.data.interpretation_export import InterpretationExportError
from geoworkbench.project.interpretation_controller import InterpretationController
from geoworkbench.services.localization import AppLanguage, Localizer


class InterpretationIntervalValues(TypedDict):
    top_depth: float
    bottom_depth: float
    interval_type: str
    label: str
    color: str
    comment: str


class InterpretationIntervalsDialog(QDialog):
    interpretation_selected = Signal(str)
    interval_selected = Signal(str, str)
    intervals_changed = Signal()

    def __init__(
        self,
        controller: InterpretationController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.localizer = Localizer.create(language)
        self._selection_guard = False
        self.setWindowTitle(self._t("interpretations.window_title"))
        self.resize(1120, 680)

        root = QVBoxLayout(self)
        interpretation_row = QHBoxLayout()
        self.interpretation_combo = QComboBox()
        self.interpretation_combo.setObjectName("interpretations-combo")
        self.interpretation_combo.currentIndexChanged.connect(self._select_interpretation)
        interpretation_row.addWidget(self.interpretation_combo, 1)
        for object_name, key, handler in (
            ("interpretations-add-button", "interpretations.add", self._add_interpretation),
            (
                "interpretations-rename-button",
                "interpretations.rename",
                self._rename_interpretation,
            ),
            (
                "interpretations-remove-button",
                "interpretations.remove",
                self._remove_interpretation,
            ),
        ):
            button = QPushButton(self._t(key))
            button.setObjectName(object_name)
            button.clicked.connect(handler)
            interpretation_row.addWidget(button)
        root.addLayout(interpretation_row)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText(self._t("interpretations.description"))
        self.description_input.editingFinished.connect(self._save_description)
        root.addWidget(self.description_input)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName("interpretation-intervals-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("interpretations.top"),
                self._t("interpretations.bottom"),
                self._t("interpretations.type"),
                self._t("interpretations.label"),
                self._t("interpretations.color"),
                self._t("interpretations.comment"),
            ]
        )
        self.table.itemSelectionChanged.connect(self._load_selected_interval)
        root.addWidget(self.table, 1)

        form = QFormLayout()
        self.top_input = self._depth_input()
        self.bottom_input = self._depth_input()
        self.type_input = QComboBox()
        self.type_input.setEditable(True)
        self.type_input.addItems(
            [
                self._t("interpretations.type_reservoir"),
                self._t("interpretations.type_fluid"),
                self._t("interpretations.type_show"),
                self._t("interpretations.type_risk"),
                self._t("interpretations.type_note"),
            ]
        )
        self.label_input = QLineEdit()
        self.color_input = QLineEdit("#fde68a")
        self.comment_input = QLineEdit()
        for label, control in (
            (self._t("interpretations.top"), self.top_input),
            (self._t("interpretations.bottom"), self.bottom_input),
            (self._t("interpretations.type"), self.type_input),
            (self._t("interpretations.label"), self.label_input),
            (self._t("interpretations.color"), self.color_input),
            (self._t("interpretations.comment"), self.comment_input),
        ):
            form.addRow(label, control)
        root.addLayout(form)

        interval_actions = QHBoxLayout()
        for object_name, key, handler in (
            ("interpretation-interval-add-button", "common.add", self._add_interval),
            (
                "interpretation-interval-update-button",
                "common.update",
                self._update_interval,
            ),
            (
                "interpretation-interval-remove-button",
                "common.remove",
                self._remove_interval,
            ),
            ("interpretation-undo-button", "common.undo", self._undo),
            ("interpretation-redo-button", "common.redo", self._redo),
        ):
            button = QPushButton(self._t(key))
            button.setObjectName(object_name)
            button.clicked.connect(handler)
            interval_actions.addWidget(button)
        root.addLayout(interval_actions)

        export_actions = QHBoxLayout()
        export_actions.addStretch(1)
        for export_format, key in (
            ("json", "interpretations.export_json"),
            ("csv", "interpretations.export_csv"),
            ("xlsx", "interpretations.export_excel"),
        ):
            button = QPushButton(self._t(key))
            button.clicked.connect(lambda checked=False, value=export_format: self._export(value))
            export_actions.addWidget(button)
        root.addLayout(export_actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._refresh_interpretations()

    def _t(self, key: str, **values: object) -> str:
        return self.localizer.text(key, **values)

    @staticmethod
    def _depth_input() -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(-100_000.0, 100_000.0)
        control.setDecimals(3)
        return control

    def _refresh_interpretations(self) -> None:
        selected = self.controller.selected_interpretation_id
        self.interpretation_combo.blockSignals(True)
        self.interpretation_combo.clear()
        try:
            interpretations = self.controller.available_interpretations()
        except RuntimeError:
            interpretations = ()
        for interpretation in interpretations:
            self.interpretation_combo.addItem(
                interpretation.name,
                interpretation.interpretation_id,
            )
        index = self.interpretation_combo.findData(selected)
        if index < 0 and self.interpretation_combo.count():
            index = 0
        if index >= 0:
            self.interpretation_combo.setCurrentIndex(index)
            self.controller.select_interpretation(str(self.interpretation_combo.itemData(index)))
        self.interpretation_combo.blockSignals(False)
        self._refresh_interpretation_details()

    def _refresh_interpretation_details(self) -> None:
        try:
            interpretation = self.controller.current_interpretation()
        except RuntimeError:
            self.description_input.clear()
            self.table.setRowCount(0)
            return
        self.description_input.setText(interpretation.description or "")
        intervals = self.controller.available_intervals()
        selected_interval_id = self.controller.selected_interval_id
        selected_row = -1
        previous_guard = self._selection_guard
        self._selection_guard = True
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(intervals))
            for row, interval in enumerate(intervals):
                values = (
                    f"{interval.top_depth:g}",
                    f"{interval.bottom_depth:g}",
                    interval.interval_type,
                    interval.label,
                    interval.color,
                    interval.comment or "",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column == 0:
                        item.setData(256, interval.interval_id)
                    self.table.setItem(row, column, item)
                if interval.interval_id == selected_interval_id:
                    selected_row = row
            if selected_row >= 0:
                self.table.selectRow(selected_row)
            else:
                self.table.clearSelection()
                self.table.setCurrentCell(-1, -1)
        finally:
            self.table.blockSignals(False)
            self._selection_guard = previous_guard
        self.table.resizeColumnsToContents()
        if selected_row >= 0:
            self._load_selected_interval()

    def _select_interpretation(self, index: int) -> None:
        interpretation_id = self.interpretation_combo.itemData(index)
        if isinstance(interpretation_id, str):
            self.controller.select_interpretation(interpretation_id)
            if not self._selection_guard:
                self.interpretation_selected.emit(interpretation_id)
        self._refresh_interpretation_details()

    def select_interpretation(self, interpretation_id: str) -> bool:
        try:
            self.controller.select_interpretation(interpretation_id)
        except (KeyError, RuntimeError):
            return False
        previous_guard = self._selection_guard
        self._selection_guard = True
        try:
            index = self.interpretation_combo.findData(interpretation_id)
            if index >= 0:
                self.interpretation_combo.setCurrentIndex(index)
            self._refresh_interpretation_details()
        finally:
            self._selection_guard = previous_guard
        return self.controller.selected_interpretation_id == interpretation_id

    def select_interval(self, interpretation_id: str, interval_id: str) -> bool:
        try:
            self.controller.select_interval(interpretation_id, interval_id)
        except (KeyError, RuntimeError):
            return False
        previous_guard = self._selection_guard
        self._selection_guard = True
        try:
            index = self.interpretation_combo.findData(interpretation_id)
            if index >= 0:
                self.interpretation_combo.setCurrentIndex(index)
            self._refresh_interpretation_details()
        finally:
            self._selection_guard = previous_guard
        return self._selected_interval_id() == interval_id

    def _add_interpretation(self) -> None:
        name, accepted = QInputDialog.getText(
            self,
            self._t("interpretations.title"),
            self._t("interpretations.name"),
        )
        if accepted and self._run(lambda: self.controller.add_interpretation(name)):
            self._refresh_interpretations()
            self.intervals_changed.emit()

    def _rename_interpretation(self) -> None:
        try:
            current = self.controller.current_interpretation()
        except RuntimeError as exc:
            QMessageBox.information(self, self._t("interpretations.title"), str(exc))
            return
        name, accepted = QInputDialog.getText(
            self,
            self._t("interpretations.title"),
            self._t("interpretations.name"),
            text=current.name,
        )
        if accepted and self._run(
            lambda: self.controller.update_interpretation(
                current.interpretation_id,
                name=name,
                description=self.description_input.text(),
            )
        ):
            self._refresh_interpretations()
            self.intervals_changed.emit()

    def _remove_interpretation(self) -> None:
        try:
            current = self.controller.current_interpretation()
        except RuntimeError as exc:
            QMessageBox.information(self, self._t("interpretations.title"), str(exc))
            return
        answer = QMessageBox.question(
            self,
            self._t("interpretations.title"),
            self._t("interpretations.confirm_remove", name=current.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer is QMessageBox.StandardButton.Yes and self._run(
            lambda: self.controller.remove_interpretation(current.interpretation_id)
        ):
            self._refresh_interpretations()
            self.intervals_changed.emit()

    def _save_description(self) -> None:
        try:
            current = self.controller.current_interpretation()
        except RuntimeError:
            return
        self._run(
            lambda: self.controller.update_interpretation(
                current.interpretation_id,
                name=current.name,
                description=self.description_input.text(),
            )
        )

    def _interval_values(self) -> InterpretationIntervalValues:
        return {
            "top_depth": self.top_input.value(),
            "bottom_depth": self.bottom_input.value(),
            "interval_type": self.type_input.currentText(),
            "label": self.label_input.text(),
            "color": self.color_input.text(),
            "comment": self.comment_input.text(),
        }

    def _add_interval(self) -> None:
        if self._run(lambda: self.controller.add_interval(**self._interval_values())):
            self.label_input.clear()
            self.comment_input.clear()
            self._refresh_interpretation_details()
            self.intervals_changed.emit()

    def _update_interval(self) -> None:
        interval_id = self._selected_interval_id()
        if interval_id is None:
            QMessageBox.information(
                self,
                self._t("interpretations.title"),
                self._t("interpretations.select_interval"),
            )
            return
        if self._run(
            lambda: self.controller.update_interval(
                interval_id,
                **self._interval_values(),
            )
        ):
            self._refresh_interpretation_details()
            self.intervals_changed.emit()

    def _remove_interval(self) -> None:
        interval_id = self._selected_interval_id()
        if interval_id is None:
            QMessageBox.information(
                self,
                self._t("interpretations.title"),
                self._t("interpretations.select_interval"),
            )
            return
        if self._run(lambda: self.controller.remove_interval(interval_id)):
            self._refresh_interpretation_details()
            self.intervals_changed.emit()

    def _selected_interval_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(256)) if item is not None else None

    def _load_selected_interval(self) -> None:
        row = self.table.currentRow()
        items = [self.table.item(row, column) for column in range(6)] if row >= 0 else []
        if len(items) != 6 or any(item is None for item in items):
            return
        values = [item.text() for item in items if item is not None]
        self.top_input.setValue(float(values[0]))
        self.bottom_input.setValue(float(values[1]))
        self.type_input.setCurrentText(values[2])
        self.label_input.setText(values[3])
        self.color_input.setText(values[4])
        self.comment_input.setText(values[5])
        interval_id = self._selected_interval_id()
        interpretation_id = self.controller.selected_interpretation_id
        if interval_id is not None and interpretation_id is not None:
            self.controller.select_interval(interpretation_id, interval_id)
            if not self._selection_guard:
                self.interval_selected.emit(interpretation_id, interval_id)

    def _undo(self) -> None:
        if self._run(self.controller.undo):
            self._refresh_interpretations()
            self.intervals_changed.emit()

    def _redo(self) -> None:
        if self._run(self.controller.redo):
            self._refresh_interpretations()
            self.intervals_changed.emit()

    def _export(self, export_format: str) -> None:
        try:
            interpretation = self.controller.current_interpretation()
        except RuntimeError as exc:
            QMessageBox.information(self, self._t("interpretations.title"), str(exc))
            return
        suffix = {"json": ".json", "csv": ".csv", "xlsx": ".xlsx"}[export_format]
        filters = {
            "json": "JSON (*.json)",
            "csv": "CSV (*.csv)",
            "xlsx": "Excel (*.xlsx)",
        }
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._t("interpretations.export_title"),
            str(Path.cwd() / f"{interpretation.name}{suffix}"),
            filters[export_format],
        )
        if not filename:
            return
        target = Path(filename)
        overwrite = False
        if target.exists():
            answer = QMessageBox.question(
                self,
                self._t("interpretations.title"),
                self._t("interpretations.confirm_overwrite", name=target.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        try:
            exported = self.controller.export_current(
                target,
                export_format,
                overwrite=overwrite,
            )
        except (
            FileExistsError,
            InterpretationExportError,
            OSError,
            RuntimeError,
            ValueError,
        ) as exc:
            QMessageBox.warning(self, self._t("interpretations.title"), str(exc))
            return
        QMessageBox.information(
            self,
            self._t("interpretations.title"),
            self._t("interpretations.exported", name=exported.name),
        )

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("interpretations.title"), str(exc))
            return False
        return True
