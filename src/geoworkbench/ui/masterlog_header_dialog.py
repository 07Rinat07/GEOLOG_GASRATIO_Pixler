from __future__ import annotations

import json

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QGraphicsScene,
    QGraphicsView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from geoworkbench.domain.models import MasterlogHeaderElement
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.printing.header_fields import resolve_header_field
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
        self.preview_scene = QGraphicsScene(self)
        self.preview = QGraphicsView(self.preview_scene)
        self.preview.setObjectName("masterlog-header-preview")
        self.preview.setMinimumWidth(360)
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
        content = QHBoxLayout()
        content.addWidget(self.list, 1)
        content.addWidget(self.preview, 2)
        layout = QVBoxLayout(self)
        layout.addLayout(content)
        layout.addLayout(buttons)
        self.resize(700, 420)
        self.refresh()

    @property
    def template(self):
        return self.controller.session.project.masterlog_templates[self.template_id]

    def refresh(self) -> None:
        self.list.clear()
        self.preview_scene.clear()
        header_width = max(
            210.0,
            max(
                (item.x_mm + item.width_mm for item in self.template.header_elements),
                default=0.0,
            ),
        )
        header_height = max(
            self.template.header_height_mm,
            max(
                (item.y_mm + item.height_mm for item in self.template.header_elements),
                default=0.0,
            ),
            1.0,
        )
        self.preview_scene.addRect(
            QRectF(0.0, 0.0, header_width, header_height),
            QPen(QColor("#334155"), 0.6),
        )
        colors = {
            "text": QColor("#dbeafe"),
            "field": QColor("#dcfce7"),
            "image": QColor("#fef3c7"),
            "line": QColor("#e2e8f0"),
        }
        for element in self.template.header_elements:
            item = QListWidgetItem(
                f"{element.element_type} | {element.x_mm:g},{element.y_mm:g} | {element.width_mm:g}×{element.height_mm:g} mm"
            )
            item.setData(Qt.ItemDataRole.UserRole, element.element_id)
            self.list.addItem(item)
            rectangle = self.preview_scene.addRect(
                QRectF(
                    element.x_mm,
                    element.y_mm,
                    element.width_mm,
                    element.height_mm,
                ),
                QPen(QColor("#475569"), 0.4),
                colors[element.element_type],
            )
            rectangle.setToolTip(json.dumps(element.properties, ensure_ascii=False))
            label = self.preview_scene.addText(self._preview_text(element))
            label.setDefaultTextColor(QColor("#0f172a"))
            label.setScale(0.35)
            label.setPos(element.x_mm + 1.0, element.y_mm + 0.5)
        self.preview_scene.setSceneRect(
            QRectF(-2.0, -2.0, header_width + 4.0, header_height + 4.0)
        )
        self.preview.fitInView(
            self.preview_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )

    def _preview_text(self, element: MasterlogHeaderElement) -> str:
        if element.element_type == "text":
            value = element.properties.get("text")
            return str(value) if isinstance(value, (str, int, float)) else "text"
        if element.element_type == "field":
            field_name = element.properties.get("field")
            if not isinstance(field_name, str):
                return "{field}"
            resolved = resolve_header_field(self.controller.session, field_name)
            return resolved if resolved is not None else "{" + field_name + "}"
        return element.element_type

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
