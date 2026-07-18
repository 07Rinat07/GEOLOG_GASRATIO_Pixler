from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

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
    QWidget,
)

from geoworkbench.project.stratigraphy_controller import (
    STRATIGRAPHY_RANKS,
    StratigraphyController,
)
from geoworkbench.services.localization import AppLanguage, Localizer


class StratigraphyValues(TypedDict):
    top_depth: float
    bottom_depth: float
    rank: str
    code: str
    name: str
    color: str
    description: str


class StratigraphyIntervalDialog(QDialog):
    def __init__(
        self,
        top_depth: float,
        bottom_depth: float,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.top_depth = top_depth
        self.bottom_depth = bottom_depth
        localizer = Localizer.create(language)
        self.setWindowTitle(
            f"{localizer.text('stratigraphy.title')} — {top_depth:g}–{bottom_depth:g} м"
        )
        self.rank_input = QComboBox()
        self.rank_input.setEditable(True)
        self.rank_input.addItems(["", *STRATIGRAPHY_RANKS])
        self.code_input = QLineEdit()
        self.name_input = QLineEdit()
        self.color_input = QLineEdit("#dbeafe")
        self.description_input = QLineEdit()
        layout = QFormLayout(self)
        for key, control in (
            ("stratigraphy.rank", self.rank_input),
            ("stratigraphy.code", self.code_input),
            ("stratigraphy.name", self.name_input),
            ("stratigraphy.color", self.color_input),
            ("stratigraphy.description", self.description_input),
        ):
            layout.addRow(localizer.text(key), control)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> StratigraphyValues:
        return {
            "top_depth": self.top_depth,
            "bottom_depth": self.bottom_depth,
            "rank": self.rank_input.currentText(),
            "code": self.code_input.text(),
            "name": self.name_input.text(),
            "color": self.color_input.text(),
            "description": self.description_input.text(),
        }


class StratigraphyDialog(QDialog):
    def __init__(
        self,
        controller: StratigraphyController,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self._t("stratigraphy.window_title"))
        self.resize(940, 560)
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, 7)
        self.table.setObjectName("stratigraphy-intervals-table")
        self.table.setHorizontalHeaderLabels(
            [
                self._t("stratigraphy.top"),
                self._t("stratigraphy.bottom"),
                self._t("stratigraphy.rank"),
                self._t("stratigraphy.code"),
                self._t("stratigraphy.name"),
                self._t("stratigraphy.color"),
                self._t("stratigraphy.description"),
            ]
        )
        self.table.itemSelectionChanged.connect(self._load_selected)
        root.addWidget(self.table)

        form = QFormLayout()
        self.top_input = self._depth_input()
        self.bottom_input = self._depth_input()
        self.rank_input = QComboBox()
        self.rank_input.setEditable(True)
        self.rank_input.addItems(["", *STRATIGRAPHY_RANKS])
        self.code_input = QLineEdit()
        self.name_input = QLineEdit()
        self.color_input = QLineEdit("#dbeafe")
        self.description_input = QLineEdit()
        for label, control in (
            (self._t("stratigraphy.top"), self.top_input),
            (self._t("stratigraphy.bottom"), self.bottom_input),
            (self._t("stratigraphy.rank"), self.rank_input),
            (self._t("stratigraphy.code"), self.code_input),
            (self._t("stratigraphy.name"), self.name_input),
            (self._t("stratigraphy.color"), self.color_input),
            (self._t("stratigraphy.description"), self.description_input),
        ):
            form.addRow(label, control)
        root.addLayout(form)

        actions = QHBoxLayout()
        for object_name, title, handler in (
            ("stratigraphy-add-button", self._t("common.add"), self._add),
            ("stratigraphy-update-button", self._t("common.update"), self._update),
            ("stratigraphy-remove-button", self._t("common.remove"), self._remove),
        ):
            button = QPushButton(title)
            button.setObjectName(object_name)
            button.clicked.connect(handler)
            actions.addWidget(button)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._t("common.close"))
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()

    def _t(self, key: str) -> str:
        return self.localizer.text(key)

    @staticmethod
    def _depth_input() -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(-100_000.0, 100_000.0)
        control.setDecimals(3)
        return control

    def _refresh(self) -> None:
        intervals = self.controller.available()
        self.table.setRowCount(len(intervals))
        for row, interval in enumerate(intervals):
            values = (
                f"{interval.top_depth:g}",
                f"{interval.bottom_depth:g}",
                interval.rank or "",
                interval.code,
                interval.name or "",
                interval.color,
                interval.description or "",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(256, interval.interval_id)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return str(item.data(256)) if item is not None else None

    def _load_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        values = [self.table.item(row, column) for column in range(7)]
        if any(item is None for item in values):
            return
        text = [item.text() for item in values if item is not None]
        self.top_input.setValue(float(text[0]))
        self.bottom_input.setValue(float(text[1]))
        self.rank_input.setCurrentText(text[2])
        self.code_input.setText(text[3])
        self.name_input.setText(text[4])
        self.color_input.setText(text[5])
        self.description_input.setText(text[6])

    def _values(self) -> StratigraphyValues:
        return {
            "top_depth": self.top_input.value(),
            "bottom_depth": self.bottom_input.value(),
            "rank": self.rank_input.currentText(),
            "code": self.code_input.text(),
            "name": self.name_input.text(),
            "color": self.color_input.text(),
            "description": self.description_input.text(),
        }

    def _add(self) -> None:
        if self._run(lambda: self.controller.add(**self._values())):
            self.code_input.clear()
            self.name_input.clear()
            self.description_input.clear()

    def _update(self) -> None:
        interval_id = self._selected_id()
        if interval_id is None:
            QMessageBox.information(
                self, self._t("stratigraphy.title"), self._t("stratigraphy.select_interval")
            )
            return
        self._run(lambda: self.controller.update(interval_id, **self._values()))

    def _remove(self) -> None:
        interval_id = self._selected_id()
        if interval_id is None:
            QMessageBox.information(
                self, self._t("stratigraphy.title"), self._t("stratigraphy.select_interval")
            )
            return
        self._run(lambda: self.controller.remove(interval_id))

    def _run(self, operation: Callable[[], object]) -> bool:
        try:
            operation()
        except (KeyError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, self._t("stratigraphy.title"), str(exc))
            return False
        self._refresh()
        return True
