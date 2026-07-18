from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFileDialog,
    QHBoxLayout,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QInputDialog,
    QVBoxLayout,
)

from geoworkbench.domain.models import MasterlogHeaderElement
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.printing.header_fields import SUPPORTED_HEADER_FIELDS, resolve_header_field
from geoworkbench.printing.image_asset_rendering import image_asset_pixmap
from geoworkbench.printing.image_assets import (
    ImageAsset,
    ImageAssetError,
    create_png_asset,
    create_svg_asset,
)
from geoworkbench.printing.masterlog_presets import BUILTIN_MASTERLOG_HEADER_PRESETS
from geoworkbench.services.localization import AppLanguage, Localizer


class HeaderElementDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        element: MasterlogHeaderElement | None = None,
        language: AppLanguage = AppLanguage.RU,
        image_assets: dict[str, ImageAsset] | None = None,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self.image_assets = image_assets or {}
        self.imported_assets: dict[str, ImageAsset] = {}
        self.setWindowTitle(self.localizer.text("masterlog_header.properties"))
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
        self.text_input = QLineEdit()
        text_value = element.properties.get("text") if element else None
        if isinstance(text_value, (str, int, float)):
            self.text_input.setText(str(text_value))
        self.field_input = QComboBox()
        self.field_input.addItems(SUPPORTED_HEADER_FIELDS)
        field_value = element.properties.get("field") if element else None
        if isinstance(field_value, str) and field_value not in SUPPORTED_HEADER_FIELDS:
            self.field_input.addItem(field_value)
        if isinstance(field_value, str):
            self.field_input.setCurrentText(field_value)
        self.text_color_input = QLineEdit("#0f172a")
        self.font_size_input = QDoubleSpinBox()
        self.font_size_input.setRange(1.0, 50.0)
        self.font_size_input.setDecimals(1)
        self.font_size_input.setValue(3.5)
        if element and element.element_type in {"text", "field"}:
            text_color = element.properties.get("color")
            font_size = element.properties.get("font_size_mm")
            if isinstance(text_color, str):
                self.text_color_input.setText(text_color)
            if isinstance(font_size, (int, float)) and not isinstance(font_size, bool):
                self.font_size_input.setValue(float(font_size))
        self.line_color_input = QLineEdit("#334155")
        self.line_width_input = QDoubleSpinBox()
        self.line_width_input.setRange(0.1, 20.0)
        self.line_width_input.setDecimals(2)
        self.line_width_input.setValue(0.6)
        if element and element.element_type == "line":
            color = element.properties.get("color")
            width = element.properties.get("width")
            if isinstance(color, str):
                self.line_color_input.setText(color)
            if isinstance(width, (int, float)) and not isinstance(width, bool):
                self.line_width_input.setValue(float(width))
        self.image_input = QComboBox()
        for asset in self.image_assets.values():
            self.image_input.addItem(asset.original_name, asset.asset_id)
        asset_ref = element.properties.get("asset_ref") if element else None
        if isinstance(asset_ref, str):
            index = self.image_input.findData(asset_ref)
            if index < 0:
                self.image_input.addItem(asset_ref, asset_ref)
                index = self.image_input.count() - 1
            self.image_input.setCurrentIndex(index)
        self.image_import_button = QPushButton(self.localizer.text("masterlog_header.import_image"))
        self.image_import_button.clicked.connect(self._import_image)
        image_row = QHBoxLayout()
        image_row.addWidget(self.image_input, 1)
        image_row.addWidget(self.image_import_button)
        layout = QFormLayout(self)
        layout.addRow(self.localizer.text("masterlog_header.type"), self.type_input)
        for label, control in zip(
            (
                self.localizer.text("masterlog_header.x"),
                self.localizer.text("masterlog_header.y"),
                self.localizer.text("masterlog_header.width"),
                self.localizer.text("masterlog_header.height"),
            ),
            self.inputs,
            strict=True,
        ):
            layout.addRow(label, control)
        self.text_label = QLabel(self.localizer.text("masterlog_header.text"))
        self.field_label = QLabel(self.localizer.text("masterlog_header.field"))
        self.properties_label = QLabel(self.localizer.text("masterlog_header.json"))
        self.line_color_label = QLabel(self.localizer.text("masterlog_header.line_color"))
        self.line_width_label = QLabel(self.localizer.text("masterlog_header.line_width"))
        self.text_color_label = QLabel(self.localizer.text("masterlog_header.text_color"))
        self.font_size_label = QLabel(self.localizer.text("masterlog_header.font_size"))
        self.image_label = QLabel(self.localizer.text("masterlog_header.image"))
        layout.addRow(self.text_label, self.text_input)
        layout.addRow(self.field_label, self.field_input)
        layout.addRow(self.text_color_label, self.text_color_input)
        layout.addRow(self.font_size_label, self.font_size_input)
        layout.addRow(self.image_label, image_row)
        layout.addRow(self.line_color_label, self.line_color_input)
        layout.addRow(self.line_width_label, self.line_width_input)
        layout.addRow(self.properties_label, self.properties_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.type_input.currentTextChanged.connect(self._update_property_inputs)
        self._update_property_inputs(self.type_input.currentText())

    def _update_property_inputs(self, element_type: str) -> None:
        self.text_input.setVisible(element_type == "text")
        self.field_input.setVisible(element_type == "field")
        self.line_color_input.setVisible(element_type == "line")
        self.line_width_input.setVisible(element_type == "line")
        self.text_color_input.setVisible(element_type in {"text", "field"})
        self.font_size_input.setVisible(element_type in {"text", "field"})
        self.properties_input.setVisible(element_type == "image")
        self.image_input.setVisible(element_type == "image")
        self.image_import_button.setVisible(element_type == "image")
        self.text_label.setVisible(element_type == "text")
        self.field_label.setVisible(element_type == "field")
        self.line_color_label.setVisible(element_type == "line")
        self.line_width_label.setVisible(element_type == "line")
        self.text_color_label.setVisible(element_type in {"text", "field"})
        self.font_size_label.setVisible(element_type in {"text", "field"})
        self.image_label.setVisible(element_type == "image")
        self.properties_label.setVisible(False)

    def _import_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.localizer.text("masterlog_header.import_image"),
            "",
            "Images (*.png *.svg)",
        )
        if not filename:
            return
        try:
            source = Path(filename)
            asset = (
                create_svg_asset(source)
                if source.suffix.casefold() == ".svg"
                else create_png_asset(source)
            )
        except (OSError, ImageAssetError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        selected_asset = self.image_assets.get(asset.asset_id)
        if selected_asset is None:
            selected_asset = self.imported_assets.setdefault(asset.asset_id, asset)
        index = self.image_input.findData(asset.asset_id)
        if index < 0:
            self.image_input.addItem(selected_asset.original_name, selected_asset.asset_id)
            index = self.image_input.count() - 1
        self.image_input.setCurrentIndex(index)

    def values(self) -> tuple[str, float, float, float, float, dict[str, object]]:
        element_type = self.type_input.currentText()
        text_style: dict[str, object] = {}
        if element_type in {"text", "field"}:
            color = QColor(self.text_color_input.text().strip())
            if not color.isValid():
                raise ValueError(self.localizer.text("masterlog_header.invalid_text_color"))
            text_style = {
                "color": color.name(),
                "font_size_mm": self.font_size_input.value(),
            }
        if element_type == "text":
            properties: dict[str, object] = {"text": self.text_input.text(), **text_style}
        elif element_type == "field":
            properties = {"field": self.field_input.currentText(), **text_style}
        elif element_type == "line":
            color = QColor(self.line_color_input.text().strip())
            if not color.isValid():
                raise ValueError(self.localizer.text("masterlog_header.invalid_color"))
            properties = {
                "color": color.name(),
                "width": self.line_width_input.value(),
            }
        elif element_type == "image":
            asset_ref = self.image_input.currentData()
            if not isinstance(asset_ref, str) or not asset_ref:
                raise ValueError(self.localizer.text("masterlog_header.select_image"))
            properties = {"asset_ref": asset_ref}
        else:
            properties = json.loads(self.properties_input.text())
            if not isinstance(properties, dict):
                raise ValueError(self.localizer.text("masterlog_header.json_object"))
        x_input, y_input, width_input, height_input = self.inputs
        return (
            element_type,
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
        self.preset_button = QPushButton(
            {
                AppLanguage.RU: "Применить шаблон шапки...",
                AppLanguage.KK: "Тақырып үлгісін қолдану...",
                AppLanguage.EN: "Apply header preset...",
            }[language]
        )
        self.preset_button.clicked.connect(self._apply_preset)
        buttons.addWidget(self.preset_button)
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
            if element.element_type == "line":
                line = self.preview_scene.addLine(
                    element.x_mm,
                    element.y_mm,
                    element.x_mm + element.width_mm,
                    element.y_mm + element.height_mm,
                    self._line_pen(element),
                )
                line.setToolTip(json.dumps(element.properties, ensure_ascii=False))
                continue
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
            if element.element_type == "image" and self._add_image_preview(element):
                continue
            label = self.preview_scene.addText(self._preview_text(element))
            color, font_size = self._text_style(element)
            label.setDefaultTextColor(color)
            label.setScale(font_size / 10.0)
            label.setPos(element.x_mm + 1.0, element.y_mm + 0.5)
        self.preview_scene.setSceneRect(QRectF(-2.0, -2.0, header_width + 4.0, header_height + 4.0))
        self.preview.fitInView(self.preview_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    @staticmethod
    def _line_pen(element: MasterlogHeaderElement) -> QPen:
        color_value = element.properties.get("color", "#334155")
        width_value = element.properties.get("width", 0.6)
        color = QColor(color_value) if isinstance(color_value, str) else QColor("#334155")
        if not color.isValid():
            color = QColor("#334155")
        width = (
            float(width_value)
            if isinstance(width_value, (int, float))
            and not isinstance(width_value, bool)
            and 0.1 <= float(width_value) <= 20.0
            else 0.6
        )
        return QPen(color, width)

    @staticmethod
    def _text_style(element: MasterlogHeaderElement) -> tuple[QColor, float]:
        color_value = element.properties.get("color", "#0f172a")
        size_value = element.properties.get("font_size_mm", 3.5)
        color = QColor(color_value) if isinstance(color_value, str) else QColor("#0f172a")
        if not color.isValid():
            color = QColor("#0f172a")
        size = (
            float(size_value)
            if isinstance(size_value, (int, float))
            and not isinstance(size_value, bool)
            and 1.0 <= float(size_value) <= 50.0
            else 3.5
        )
        return color, size

    def _add_image_preview(self, element: MasterlogHeaderElement) -> bool:
        asset_ref = element.properties.get("asset_ref")
        asset = (
            self.controller.session.image_assets.get(asset_ref)
            if isinstance(asset_ref, str)
            else None
        )
        if asset is None:
            return False
        pixmap = image_asset_pixmap(asset)
        if pixmap.isNull():
            return False
        item = self.preview_scene.addPixmap(pixmap)
        scale = min(element.width_mm / pixmap.width(), element.height_mm / pixmap.height())
        item.setScale(scale)
        item.setPos(element.x_mm, element.y_mm)
        item.setToolTip(asset.original_name)
        return True

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
        dialog = HeaderElementDialog(
            self,
            language=self.localizer.language,
            image_assets=self.controller.session.image_assets,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply(dialog, None)

    def _apply_preset(self) -> None:
        presets = BUILTIN_MASTERLOG_HEADER_PRESETS
        labels = [
            f"{item.name(self.localizer.language)} — {item.description(self.localizer.language)}"
            for item in presets
        ]
        selected, accepted = QInputDialog.getItem(
            self,
            self.preset_button.text().replace("...", ""),
            self.preset_button.text(),
            labels,
            editable=False,
        )
        if not accepted:
            return
        question = {
            AppLanguage.RU: "Заменить текущую шапку независимой копией выбранного шаблона?",
            AppLanguage.KK: "Ағымдағы тақырыпты таңдалған үлгінің тәуелсіз көшірмесімен ауыстыру керек пе?",
            AppLanguage.EN: "Replace the current header with an independent copy of this preset?",
        }[self.localizer.language]
        if (
            QMessageBox.question(self, self.windowTitle(), question)
            != QMessageBox.StandardButton.Yes
        ):
            return
        preset = presets[labels.index(selected)]
        self.controller.apply_header_preset(self.template_id, preset.preset_id)
        self.refresh()

    def _edit(self) -> None:
        element = self._selected()
        if element:
            dialog = HeaderElementDialog(
                self,
                element=element,
                language=self.localizer.language,
                image_assets=self.controller.session.image_assets,
            )
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
        else:
            if dialog.imported_assets:
                self.controller.session.image_assets.update(dialog.imported_assets)
                self.controller.session.dirty = True
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
