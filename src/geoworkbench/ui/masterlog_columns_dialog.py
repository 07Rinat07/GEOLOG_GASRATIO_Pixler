from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from geoworkbench.domain.models import MasterlogColumnTemplate, MasterlogTemplate
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.services.localization import AppLanguage, Localizer


class ColumnPropertiesDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        column: MasterlogColumnTemplate | None = None,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        localizer = Localizer.create(language)
        self.setWindowTitle(localizer.text("masterlog_columns.properties"))
        self.title_input = QLineEdit(column.title if column else "")
        self.type_input = QComboBox()
        self.type_input.setEditable(True)
        self.type_input.addItems(
            [
                "curves",
                "depth",
                "stratigraphy",
                "lithology",
                "cuttings",
                "calcimetry",
                "lba",
                "text",
            ]
        )
        if column:
            self.type_input.setCurrentText(column.column_type)
        self.width_input = QDoubleSpinBox()
        self.width_input.setRange(5.0, 200.0)
        self.width_input.setSuffix(" mm")
        self.width_input.setValue(column.width_mm if column else 30.0)
        self.curves_input = QLineEdit(", ".join(column.curve_mnemonics) if column else "")
        self.scale_input = QComboBox()
        self.scale_input.addItem(localizer.text("inspector.linear"), "linear")
        self.scale_input.addItem(localizer.text("inspector.logarithmic"), "logarithmic")
        self.scale_input.setCurrentIndex(
            self.scale_input.findData(column.x_scale if column else "linear")
        )
        self.auto_range_input = QCheckBox(localizer.text("common.auto"))
        self.auto_range_input.setChecked(
            column is None or column.x_min is None or column.x_max is None
        )
        self.minimum_input = QDoubleSpinBox()
        self.maximum_input = QDoubleSpinBox()
        for control in (self.minimum_input, self.maximum_input):
            control.setRange(-1e12, 1e12)
            control.setDecimals(6)
        self.minimum_input.setValue(column.x_min if column and column.x_min is not None else 0.1)
        self.maximum_input.setValue(column.x_max if column and column.x_max is not None else 100.0)
        self.legend_input = QCheckBox(localizer.text("masterlog_columns.show_legend"))
        self.legend_input.setChecked(column.show_legend if column else True)
        self.color_input = QLineEdit(column.line_color if column else "#2563eb")
        self.line_width_input = QDoubleSpinBox()
        self.line_width_input.setRange(0.5, 10.0)
        self.line_width_input.setDecimals(1)
        self.line_width_input.setValue(column.line_width if column else 1.5)
        self.line_style_input = QComboBox()
        for value in ("solid", "dash", "dot", "dash_dot"):
            self.line_style_input.addItem(localizer.text(f"inspector.line_style.{value}"), value)
        self.line_style_input.setCurrentIndex(
            self.line_style_input.findData(column.line_style if column else "solid")
        )
        self.auto_range_input.toggled.connect(self._update_range_enabled)
        layout = QFormLayout(self)
        layout.addRow(localizer.text("masterlog_columns.name"), self.title_input)
        layout.addRow(localizer.text("inspector.type"), self.type_input)
        layout.addRow(localizer.text("inspector.width"), self.width_input)
        layout.addRow(localizer.text("inspector.curves"), self.curves_input)
        layout.addRow(localizer.text("inspector.x_scale"), self.scale_input)
        layout.addRow(self.auto_range_input)
        layout.addRow(localizer.text("inspector.x_minimum"), self.minimum_input)
        layout.addRow(localizer.text("inspector.x_maximum"), self.maximum_input)
        layout.addRow(self.legend_input)
        layout.addRow(localizer.text("inspector.color"), self.color_input)
        layout.addRow(localizer.text("inspector.line_width"), self.line_width_input)
        layout.addRow(localizer.text("inspector.line_style"), self.line_style_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self._update_range_enabled(self.auto_range_input.isChecked())

    def values(
        self,
    ) -> tuple[
        str,
        str,
        float,
        list[str],
        str,
        float | None,
        float | None,
        bool,
        str,
        float,
        str,
    ]:
        curves = [value.strip() for value in self.curves_input.text().split(",")]
        automatic = self.auto_range_input.isChecked()
        return (
            self.title_input.text(),
            self.type_input.currentText(),
            self.width_input.value(),
            [value for value in curves if value],
            str(self.scale_input.currentData()),
            None if automatic else self.minimum_input.value(),
            None if automatic else self.maximum_input.value(),
            self.legend_input.isChecked(),
            self.color_input.text().strip(),
            self.line_width_input.value(),
            str(self.line_style_input.currentData()),
        )

    def _update_range_enabled(self, automatic: bool) -> None:
        self.minimum_input.setEnabled(not automatic)
        self.maximum_input.setEnabled(not automatic)


class MasterlogColumnsDialog(QDialog):
    def __init__(
        self,
        controller: MasterlogTemplateController,
        template_id: str,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.template_id = template_id
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self.localizer.text("masterlog_columns.title"))
        self.resize(680, 420)
        self.list = QListWidget()
        buttons = QHBoxLayout()
        for text, handler in (
            (self.localizer.text("common.create"), self._add),
            (self.localizer.text("common.edit"), self._edit),
            ("←", lambda: self._move(-1)),
            ("→", lambda: self._move(1)),
            (self.localizer.text("common.delete"), self._remove),
        ):
            button = QPushButton(text)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.refresh()

    @property
    def template(self) -> MasterlogTemplate:
        return self.controller.session.project.masterlog_templates[self.template_id]

    def refresh(self) -> None:
        self.list.clear()
        for column in self.template.columns:
            curves = ", ".join(column.curve_mnemonics) or "—"
            item = QListWidgetItem(
                f"{column.title} | {column.column_type} | {column.width_mm:g} mm | {curves}"
            )
            item.setData(Qt.ItemDataRole.UserRole, column.column_id)
            self.list.addItem(item)

    def _selected_column(self) -> MasterlogColumnTemplate | None:
        item = self.list.currentItem()
        if item is None:
            QMessageBox.information(self, self.windowTitle(), "Выберите колонку")
            return None
        column_id = str(item.data(Qt.ItemDataRole.UserRole))
        return next(column for column in self.template.columns if column.column_id == column_id)

    def _add(self) -> None:
        dialog = ColumnPropertiesDialog(self, language=self.localizer.language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        (
            title,
            column_type,
            width,
            curves,
            scale,
            x_min,
            x_max,
            legend,
            color,
            line_width,
            line_style,
        ) = dialog.values()
        self._run(
            lambda: self.controller.add_column(
                self.template_id,
                title=title,
                column_type=column_type,
                width_mm=width,
                curve_mnemonics=curves,
                x_scale=scale,
                x_min=x_min,
                x_max=x_max,
                show_legend=legend,
                line_color=color,
                line_width=line_width,
                line_style=line_style,
            )
        )

    def _edit(self) -> None:
        column = self._selected_column()
        if column is None:
            return
        dialog = ColumnPropertiesDialog(self, column=column, language=self.localizer.language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        (
            title,
            column_type,
            width,
            curves,
            scale,
            x_min,
            x_max,
            legend,
            color,
            line_width,
            line_style,
        ) = dialog.values()
        self._run(
            lambda: self.controller.update_column(
                self.template_id,
                column.column_id,
                title=title,
                column_type=column_type,
                width_mm=width,
                curve_mnemonics=curves,
                x_scale=scale,
                x_min=x_min,
                x_max=x_max,
                show_legend=legend,
                line_color=color,
                line_width=line_width,
                line_style=line_style,
            )
        )

    def _remove(self) -> None:
        column = self._selected_column()
        if column is not None:
            self._run(lambda: self.controller.remove_column(self.template_id, column.column_id))

    def _move(self, offset: int) -> None:
        column = self._selected_column()
        if column is not None:
            self._run(
                lambda: self.controller.move_column(self.template_id, column.column_id, offset)
            )

    def _run(self, operation: Callable[[], object]) -> None:
        try:
            operation()
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
        self.refresh()
