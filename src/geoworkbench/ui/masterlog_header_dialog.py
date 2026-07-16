from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from geoworkbench.domain.models import MasterlogHeaderElement
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.services.localization import AppLanguage, Localizer


class HeaderElementDialog(QDialog):
    def __init__(self, parent=None, *, element: MasterlogHeaderElement | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Свойства элемента шапки")
        self.type_input = QComboBox()
        self.type_input.addItems(["text", "field", "image", "line"])
        if element:
            self.type_input.setCurrentText(element.element_type)
        self.inputs = [QDoubleSpinBox() for _ in range(4)]
        for control in self.inputs:
            control.setRange(0.0, 5000.0)
            control.setDecimals(2)
        values = (
            (element.x_mm, element.y_mm, element.width_mm, element.height_mm)
            if element
            else (0.0, 0.0, 30.0, 10.0)
        )
        for control, value in zip(self.inputs, values, strict=True):
            control.setValue(value)
        self.properties_input = QLineEdit(
            json.dumps(element.properties, ensure_ascii=False) if element else "{}"
        )
        layout = QFormLayout(self)
        layout.addRow("Тип", self.type_input)
        for label, control in zip(
            ("X, мм", "Y, мм", "Ширина, мм", "Высота, мм"), self.inputs, strict=True
        ):
            layout.addRow(label, control)
        layout.addRow("Свойства JSON", self.properties_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> tuple[str, float, float, float, float, dict[str, object]]:
        properties = json.loads(self.properties_input.text())
        if not isinstance(properties, dict):
            raise ValueError("Свойства должны быть JSON-объектом")
        x_input, y_input, width_input, height_input = self.inputs
        return (
            self.type_input.currentText(),
            x_input.value(),
            y_input.value(),
            width_input.value(),
            height_input.value(),
            properties,
        )


class MasterlogHeaderDialog(QDialog):
    def __init__(
        self,
        controller: MasterlogTemplateController,
        template_id: str,
        parent=None,
        *,
        language: AppLanguage = AppLanguage.RU,
    ) -> None:
        super().__init__(parent)
        self.controller, self.template_id = controller, template_id
        self.localizer = Localizer.create(language)
        self.setWindowTitle(self.localizer.text("masterlog_header.title"))
        self.list = QListWidget()
        buttons = QHBoxLayout()
        for text, callback in (
            ("+", self._add),
            ("Изменить", self._edit),
            ("↑", lambda: self._move(-1)),
            ("↓", lambda: self._move(1)),
            ("−", self._remove),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.resize(700, 420)
        self.refresh()

    @property
    def template(self):
        return self.controller.session.project.masterlog_templates[self.template_id]

    def refresh(self) -> None:
        self.list.clear()
        for element in self.template.header_elements:
            item = QListWidgetItem(
                f"{element.element_type} | {element.x_mm:g},{element.y_mm:g} | {element.width_mm:g}×{element.height_mm:g} mm"
            )
            item.setData(Qt.ItemDataRole.UserRole, element.element_id)
            self.list.addItem(item)

    def _selected(self) -> MasterlogHeaderElement | None:
        item = self.list.currentItem()
        if item is None:
            return None
        element_id = str(item.data(Qt.ItemDataRole.UserRole))
        return next(
            value for value in self.template.header_elements if value.element_id == element_id
        )

    def _add(self) -> None:
        dialog = HeaderElementDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply(dialog, None)

    def _edit(self) -> None:
        element = self._selected()
        if element:
            dialog = HeaderElementDialog(self, element=element)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._apply(dialog, element.element_id)

    def _apply(self, dialog: HeaderElementDialog, element_id: str | None) -> None:
        try:
            kind, x, y, width, height, properties = dialog.values()
            if element_id is None:
                self.controller.add_header_element(
                    self.template_id,
                    element_type=kind,
                    x_mm=x,
                    y_mm=y,
                    width_mm=width,
                    height_mm=height,
                    properties=properties,
                )
            else:
                self.controller.update_header_element(
                    self.template_id,
                    element_id,
                    element_type=kind,
                    x_mm=x,
                    y_mm=y,
                    width_mm=width,
                    height_mm=height,
                    properties=properties,
                )
        except (ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
        self.refresh()

    def _remove(self) -> None:
        element = self._selected()
        if element:
            self.controller.remove_header_element(self.template_id, element.element_id)
            self.refresh()

    def _move(self, offset: int) -> None:
        element = self._selected()
        if element:
            self.controller.move_header_element(self.template_id, element.element_id, offset)
            self.refresh()
