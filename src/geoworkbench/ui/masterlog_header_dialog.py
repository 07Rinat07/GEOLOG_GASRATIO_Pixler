from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QBrush, QPen, QTransform, QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.domain.models import MasterlogHeaderElement
from geoworkbench.domain.text_presentation import (
    TEXT_ORIENTATIONS,
    TEXT_VERTICAL_POSITIONS,
    text_angle,
    text_position_fraction,
)
from geoworkbench.printing.header_fields import (
    SUPPORTED_HEADER_FIELDS,
    editable_header_field_definitions,
    header_field_label,
    resolve_header_field,
)
from geoworkbench.printing.image_asset_rendering import image_asset_pixmap
from geoworkbench.printing.image_assets import (
    ImageAsset,
    ImageAssetError,
    create_raster_asset,
    create_svg_asset,
)
from geoworkbench.printing.masterlog_presets import BUILTIN_MASTERLOG_HEADER_PRESETS
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.lithotype_catalog_controller import (
    CatalogLithotype,
    LithotypeCatalogController,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.tablet.lithology_patterns import lithology_brush
from geoworkbench.ui.lithotype_visuals import configure_lithotype_combo, lithotype_icon


_TEXT = {
    AppLanguage.RU: {
        "data": "Данные шапки...",
        "height": "Высота шапки, мм",
        "duplicate": "Дублировать",
        "fit": "Показать целиком",
        "snap": "Привязка к сетке",
        "grid": "Шаг, мм",
        "clear": "Очистить введённые значения",
        "data_title": "Данные шапки формы",
        "drag_hint": "Элементы можно перемещать мышью. Двойной щелчок открывает свойства.",
        "delete_confirm": "Удалить выбранный элемент шапки?",
        "bold": "Полужирный",
        "alignment": "Выравнивание",
        "text_orientation": "Направление текста",
        "text_position": "Положение текста",
        "horizontal": "Горизонтально (0°)",
        "bottom_to_top": "Вертикально снизу вверх (90°)",
        "top_to_bottom": "Вертикально сверху вниз (90°)",
        "near_top": "Ближе к верху",
        "middle": "По центру",
        "near_bottom": "Ближе к низу",
        "left": "Слева",
        "center": "По центру",
        "right": "Справа",
        "frame": "Рамка",
        "background": "Фон (#RRGGBB или пусто)",
        "unit_mm": "мм",
        "type_text": "Текст",
        "type_field": "Динамическое поле",
        "type_image": "Изображение",
        "type_line": "Линия",
        "type_lithotype_swatch": "Образец литотипа / рисунок породы",
        "type_lithology_legend": "Литологическая легенда",
        "type_lba_legend": "Легенда ЛБА",
    },
    AppLanguage.KK: {
        "data": "Тақырып деректері...",
        "height": "Тақырып биіктігі, мм",
        "duplicate": "Көшірмелеу",
        "fit": "Толық көрсету",
        "snap": "Торға байлау",
        "grid": "Қадам, мм",
        "clear": "Енгізілген мәндерді тазалау",
        "data_title": "Пішін тақырыбының деректері",
        "drag_hint": "Элементтерді тінтуірмен жылжытуға болады. Қос шерту қасиеттерді ашады.",
        "delete_confirm": "Таңдалған тақырып элементін жою керек пе?",
        "bold": "Қалың",
        "alignment": "Туралау",
        "text_orientation": "Мәтін бағыты",
        "text_position": "Мәтін орны",
        "horizontal": "Көлденең (0°)",
        "bottom_to_top": "Төменнен жоғары тік (90°)",
        "top_to_bottom": "Жоғарыдан төмен тік (90°)",
        "near_top": "Жоғарыға жақын",
        "middle": "Ортада",
        "near_bottom": "Төменге жақын",
        "left": "Сол жақ",
        "center": "Ортада",
        "right": "Оң жақ",
        "frame": "Жақтау",
        "background": "Фон (#RRGGBB немесе бос)",
        "unit_mm": "мм",
        "type_text": "Мәтін",
        "type_field": "Динамикалық өріс",
        "type_image": "Сурет",
        "type_line": "Сызық",
        "type_lithotype_swatch": "Литотип үлгісі / жыныс суреті",
        "type_lithology_legend": "Литология аңызы",
        "type_lba_legend": "ЛБА аңызы",
    },
    AppLanguage.EN: {
        "data": "Header data...",
        "height": "Header height, mm",
        "duplicate": "Duplicate",
        "fit": "Fit all",
        "snap": "Snap to grid",
        "grid": "Step, mm",
        "clear": "Clear entered values",
        "data_title": "Form header data",
        "drag_hint": "Drag elements with the mouse. Double-click opens properties.",
        "delete_confirm": "Delete the selected header element?",
        "bold": "Bold",
        "alignment": "Alignment",
        "text_orientation": "Text direction",
        "text_position": "Text position",
        "horizontal": "Horizontal (0°)",
        "bottom_to_top": "Vertical bottom to top (90°)",
        "top_to_bottom": "Vertical top to bottom (90°)",
        "near_top": "Near top",
        "middle": "Centred",
        "near_bottom": "Near bottom",
        "left": "Left",
        "center": "Center",
        "right": "Right",
        "frame": "Border",
        "background": "Background (#RRGGBB or empty)",
        "unit_mm": "mm",
        "type_text": "Text",
        "type_field": "Dynamic field",
        "type_image": "Image",
        "type_line": "Line",
        "type_lithotype_swatch": "Lithotype swatch / rock pattern",
        "type_lithology_legend": "Lithology legend",
        "type_lba_legend": "LBA legend",
    },
}


class _DataComboBox(QComboBox):
    """QComboBox whose compatibility ``setCurrentText`` also resolves item data."""

    def setCurrentText(self, text: str) -> None:  # noqa: N802 - Qt compatibility API
        index = self.findData(text)
        if index >= 0:
            self.setCurrentIndex(index)
            return
        super().setCurrentText(text)


class HeaderElementDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        element: MasterlogHeaderElement | None = None,
        language: AppLanguage = AppLanguage.RU,
        image_assets: dict[str, ImageAsset] | None = None,
        lithotypes: dict[str, CatalogLithotype] | None = None,
    ) -> None:
        super().__init__(parent)
        self.localizer = Localizer.create(language)
        self._original_properties = dict(element.properties) if element is not None else {}
        self.image_assets = image_assets or {}
        self.lithotypes = lithotypes or {}
        self.imported_assets: dict[str, ImageAsset] = {}
        self.setWindowTitle(self.localizer.text("masterlog_header.properties"))
        self.setMinimumWidth(480)

        self.type_input = _DataComboBox()
        for element_type in (
            "text",
            "field",
            "image",
            "line",
            "lithotype_swatch",
            "lithology_legend",
            "lba_legend",
        ):
            self.type_input.addItem(
                _TEXT[language][f"type_{element_type}"],
                element_type,
            )
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
        for field_name in SUPPORTED_HEADER_FIELDS:
            label = header_field_label(field_name, language)
            self.field_input.addItem(f"{label} — {field_name}", field_name)
        field_value = element.properties.get("field") if element else None
        if isinstance(field_value, str):
            index = self.field_input.findData(field_value)
            if index < 0:
                self.field_input.addItem(field_value, field_value)
                index = self.field_input.count() - 1
            self.field_input.setCurrentIndex(index)

        self.text_color_input = QLineEdit("#0f172a")
        self.font_size_input = QDoubleSpinBox()
        self.font_size_input.setRange(1.0, 50.0)
        self.font_size_input.setDecimals(1)
        self.font_size_input.setValue(3.5)
        self.bold_input = QCheckBox(_TEXT[language]["bold"])
        self.alignment_input = QComboBox()
        self.alignment_input.addItem(_TEXT[language]["left"], "left")
        self.alignment_input.addItem(_TEXT[language]["center"], "center")
        self.alignment_input.addItem(_TEXT[language]["right"], "right")
        self.text_orientation_input = QComboBox()
        orientation_labels = {
            "horizontal": _TEXT[language]["horizontal"],
            "vertical_bottom_to_top": _TEXT[language]["bottom_to_top"],
            "vertical_top_to_bottom": _TEXT[language]["top_to_bottom"],
        }
        for orientation_value in TEXT_ORIENTATIONS:
            self.text_orientation_input.addItem(
                orientation_labels[orientation_value], orientation_value
            )
        self.text_position_input = QComboBox()
        position_labels = {
            "top": _TEXT[language]["near_top"],
            "center": _TEXT[language]["middle"],
            "bottom": _TEXT[language]["near_bottom"],
        }
        for position_value in TEXT_VERTICAL_POSITIONS:
            self.text_position_input.addItem(
                position_labels[position_value], position_value
            )
        # The centre is the neutral/default placement for newly created text.
        # TEXT_VERTICAL_POSITIONS is ordered for presentation, so select the
        # model default explicitly instead of relying on the first item.
        default_position_index = self.text_position_input.findData("center")
        self.text_position_input.setCurrentIndex(max(0, default_position_index))
        self.frame_input = QCheckBox(_TEXT[language]["frame"])
        self.background_input = QLineEdit()

        if element and element.element_type in {
            "text",
            "field",
            "lithotype_swatch",
            "lithology_legend",
            "lba_legend",
        }:
            text_color = element.properties.get("color")
            font_size = element.properties.get("font_size_mm")
            if isinstance(text_color, str):
                self.text_color_input.setText(text_color)
            if isinstance(font_size, (int, float)) and not isinstance(font_size, bool):
                self.font_size_input.setValue(float(font_size))
            self.bold_input.setChecked(bool(element.properties.get("bold", False)))
            alignment = element.properties.get("alignment", "left")
            alignment_index = self.alignment_input.findData(alignment)
            self.alignment_input.setCurrentIndex(max(0, alignment_index))
            orientation_index = self.text_orientation_input.findData(
                element.properties.get("text_orientation", "horizontal")
            )
            self.text_orientation_input.setCurrentIndex(max(0, orientation_index))
            position_index = self.text_position_input.findData(
                element.properties.get("text_position", "center")
            )
            self.text_position_input.setCurrentIndex(max(0, position_index))
            self.frame_input.setChecked(bool(element.properties.get("frame", False)))
            background = element.properties.get("background")
            if isinstance(background, str):
                self.background_input.setText(background)

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

        self.legend_scope_input = QComboBox()
        self.legend_scope_input.addItem(self.localizer.text("masterlog_header.legend_used"), "used")
        self.legend_scope_input.addItem(self.localizer.text("masterlog_header.legend_all"), "all")
        self.legend_scope_input.addItem(
            self.localizer.text("masterlog_header.legend_manual"), "manual"
        )
        self.legend_scope_input.addItem(
            self.localizer.text("masterlog_header.legend_used_manual"), "used_manual"
        )
        scope = element.properties.get("scope") if element else "used"
        scope_index = self.legend_scope_input.findData(scope)
        self.legend_scope_input.setCurrentIndex(max(0, scope_index))
        self.legend_columns_input = QSpinBox()
        self.legend_columns_input.setRange(1, 12)
        columns = element.properties.get("columns") if element else 4
        self.legend_columns_input.setValue(
            int(columns)
            if isinstance(columns, int) and not isinstance(columns, bool) and 1 <= columns <= 12
            else 4
        )
        self.legend_code_input = QCheckBox(self.localizer.text("masterlog_header.legend_show_code"))
        show_code = element.properties.get("show_code") if element else True
        self.legend_code_input.setChecked(show_code if isinstance(show_code, bool) else True)
        self.legend_manual_input = QListWidget()
        self.legend_manual_input.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.legend_manual_input.setMinimumHeight(120)
        selected_lithotypes = {
            str(value)
            for value in (element.properties.get("selected_lithotype_ids", []) if element else [])
            if isinstance(value, str)
        }
        for definition in sorted(
            self.lithotypes.values(), key=lambda item: item.name_ru.casefold()
        ):
            names = {
                AppLanguage.RU: definition.name_ru,
                AppLanguage.KK: definition.name_kk or definition.name_ru,
                AppLanguage.EN: definition.name_en or definition.name_ru,
            }
            item = QListWidgetItem(f"{definition.code} — {names[language]}")
            item.setData(Qt.ItemDataRole.UserRole, definition.lithotype_id)
            item.setSelected(definition.lithotype_id in selected_lithotypes)
            self.legend_manual_input.addItem(item)

        self.lithotype_input = QComboBox()
        configure_lithotype_combo(self.lithotype_input)
        self.lithotype_input.setMinimumContentsLength(24)
        for definition in sorted(
            self.lithotypes.values(), key=lambda item: item.name_ru.casefold()
        ):
            names = {
                AppLanguage.RU: definition.name_ru,
                AppLanguage.KK: definition.name_kk or definition.name_ru,
                AppLanguage.EN: definition.name_en or definition.name_ru,
            }
            self.lithotype_input.addItem(
                lithotype_icon(definition),
                f"{definition.code} — {names[language]}",
                definition.lithotype_id,
            )
        selected_lithotype_id = element.properties.get("lithotype_id") if element else None
        if isinstance(selected_lithotype_id, str):
            lithotype_index = self.lithotype_input.findData(selected_lithotype_id)
            if lithotype_index >= 0:
                self.lithotype_input.setCurrentIndex(lithotype_index)
        self.lithotype_label_mode_input = QComboBox()
        for caption, label_mode_value in (
            (
                {
                    AppLanguage.RU: "Только рисунок",
                    AppLanguage.KK: "Тек сурет",
                    AppLanguage.EN: "Pattern only",
                }[language],
                "pattern_only",
            ),
            (
                {
                    AppLanguage.RU: "Рисунок и название",
                    AppLanguage.KK: "Сурет және атау",
                    AppLanguage.EN: "Pattern and name",
                }[language],
                "pattern_name",
            ),
            (
                {
                    AppLanguage.RU: "Рисунок, код и название",
                    AppLanguage.KK: "Сурет, код және атау",
                    AppLanguage.EN: "Pattern, code and name",
                }[language],
                "pattern_code_name",
            ),
        ):
            self.lithotype_label_mode_input.addItem(caption, label_mode_value)
        swatch_mode = element.properties.get("display_mode") if element else "pattern_code_name"
        swatch_mode_index = self.lithotype_label_mode_input.findData(swatch_mode)
        self.lithotype_label_mode_input.setCurrentIndex(max(0, swatch_mode_index))

        self.image_input = QComboBox()
        self.image_input.addItem(
            {
                AppLanguage.RU: "— Загрузить изображение —",
                AppLanguage.KK: "— Суретті жүктеу —",
                AppLanguage.EN: "— Load image —",
            }[language],
            "",
        )
        for asset in self.image_assets.values():
            self.image_input.addItem(asset.original_name, asset.asset_id)
        asset_ref = element.properties.get("asset_ref") if element else None
        if isinstance(asset_ref, str) and asset_ref:
            index = self.image_input.findData(asset_ref)
            if index < 0:
                self.image_input.addItem(asset_ref, asset_ref)
                index = self.image_input.count() - 1
            self.image_input.setCurrentIndex(index)
        elif not (element is not None and element.properties.get("optional") is True):
            if self.image_input.count() > 1:
                self.image_input.setCurrentIndex(1)
        self.image_mode_input = QComboBox()
        self.image_mode_input.addItem("Fit / вписать", "fit")
        self.image_mode_input.addItem("Fill / заполнить", "fill")
        self.image_mode_input.addItem("Stretch / растянуть", "stretch")
        image_mode = element.properties.get("mode", "fit") if element else "fit"
        self.image_mode_input.setCurrentIndex(max(0, self.image_mode_input.findData(image_mode)))
        self.image_rotation_input = QDoubleSpinBox()
        self.image_rotation_input.setRange(-360.0, 360.0)
        self.image_rotation_input.setDecimals(1)
        rotation = element.properties.get("rotation", 0.0) if element else 0.0
        if isinstance(rotation, (int, float)) and not isinstance(rotation, bool):
            self.image_rotation_input.setValue(float(rotation))
        self.image_opacity_input = QDoubleSpinBox()
        self.image_opacity_input.setRange(0.0, 100.0)
        self.image_opacity_input.setSuffix(" %")
        opacity = element.properties.get("opacity", 1.0) if element else 1.0
        if isinstance(opacity, (int, float)) and not isinstance(opacity, bool):
            self.image_opacity_input.setValue(max(0.0, min(100.0, float(opacity) * 100.0)))
        else:
            self.image_opacity_input.setValue(100.0)
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
        self.legend_scope_label = QLabel(self.localizer.text("masterlog_header.legend_scope"))
        self.legend_columns_label = QLabel(self.localizer.text("masterlog_header.legend_columns"))
        self.legend_manual_label = QLabel(self.localizer.text("masterlog_header.legend_manual_items"))
        self.lithotype_label = QLabel(
            {
                AppLanguage.RU: "Литотип",
                AppLanguage.KK: "Литотип",
                AppLanguage.EN: "Lithotype",
            }[language]
        )
        self.lithotype_mode_label = QLabel(
            {
                AppLanguage.RU: "Вид вставки",
                AppLanguage.KK: "Кірістіру түрі",
                AppLanguage.EN: "Insert mode",
            }[language]
        )
        self.alignment_label = QLabel(_TEXT[language]["alignment"])
        self.text_orientation_label = QLabel(_TEXT[language]["text_orientation"])
        self.text_position_label = QLabel(_TEXT[language]["text_position"])
        self.background_label = QLabel(_TEXT[language]["background"])

        layout.addRow(self.text_label, self.text_input)
        layout.addRow(self.field_label, self.field_input)
        layout.addRow(self.text_color_label, self.text_color_input)
        layout.addRow(self.font_size_label, self.font_size_input)
        layout.addRow(self.bold_input)
        layout.addRow(self.alignment_label, self.alignment_input)
        layout.addRow(self.text_orientation_label, self.text_orientation_input)
        layout.addRow(self.text_position_label, self.text_position_input)
        layout.addRow(self.frame_input)
        layout.addRow(self.background_label, self.background_input)
        layout.addRow(self.image_label, image_row)
        self.image_mode_label = QLabel("Image mode")
        self.image_rotation_label = QLabel("Rotation, °")
        self.image_opacity_label = QLabel("Opacity")
        layout.addRow(self.image_mode_label, self.image_mode_input)
        layout.addRow(self.image_rotation_label, self.image_rotation_input)
        layout.addRow(self.image_opacity_label, self.image_opacity_input)
        layout.addRow(self.line_color_label, self.line_color_input)
        layout.addRow(self.line_width_label, self.line_width_input)
        layout.addRow(self.legend_scope_label, self.legend_scope_input)
        layout.addRow(self.legend_columns_label, self.legend_columns_input)
        layout.addRow(self.legend_code_input)
        layout.addRow(self.legend_manual_label, self.legend_manual_input)
        layout.addRow(self.lithotype_label, self.lithotype_input)
        layout.addRow(self.lithotype_mode_label, self.lithotype_label_mode_input)
        layout.addRow(self.properties_label, self.properties_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.type_input.currentIndexChanged.connect(
            lambda _index: self._update_property_inputs(
                str(self.type_input.currentData() or "text")
            )
        )
        self.legend_scope_input.currentIndexChanged.connect(self._update_legend_manual_visibility)
        self._update_property_inputs(str(self.type_input.currentData() or "text"))

    def _update_property_inputs(self, element_type: str) -> None:
        self.text_input.setVisible(element_type == "text")
        self.field_input.setVisible(element_type == "field")
        self.line_color_input.setVisible(element_type == "line")
        self.line_width_input.setVisible(element_type == "line")
        has_text_style = element_type in {
            "text",
            "field",
            "lithotype_swatch",
            "lithology_legend",
            "lba_legend",
        }
        for control in (
            self.text_color_input,
            self.font_size_input,
            self.bold_input,
            self.alignment_input,
            self.frame_input,
            self.background_input,
        ):
            control.setVisible(has_text_style)
        has_text_direction = element_type in {"text", "field", "lithotype_swatch"}
        self.text_orientation_input.setVisible(has_text_direction)
        self.text_position_input.setVisible(has_text_direction)
        self.properties_input.setVisible(False)
        self.image_input.setVisible(element_type == "image")
        self.image_import_button.setVisible(element_type == "image")
        for control in (self.image_mode_input, self.image_rotation_input, self.image_opacity_input):
            control.setVisible(element_type == "image")
        self.text_label.setVisible(element_type == "text")
        self.field_label.setVisible(element_type == "field")
        self.line_color_label.setVisible(element_type == "line")
        self.line_width_label.setVisible(element_type == "line")
        self.text_color_label.setVisible(has_text_style)
        self.font_size_label.setVisible(has_text_style)
        self.alignment_label.setVisible(has_text_style)
        self.text_orientation_label.setVisible(has_text_direction)
        self.text_position_label.setVisible(has_text_direction)
        self.background_label.setVisible(has_text_style)
        self.image_label.setVisible(element_type == "image")
        for label in (self.image_mode_label, self.image_rotation_label, self.image_opacity_label):
            label.setVisible(element_type == "image")
        is_lithology = element_type == "lithology_legend"
        self.legend_scope_input.setVisible(is_lithology)
        self.legend_columns_input.setVisible(is_lithology)
        self.legend_code_input.setVisible(is_lithology)
        self.legend_scope_label.setVisible(is_lithology)
        self.legend_columns_label.setVisible(is_lithology)
        is_lithotype_swatch = element_type == "lithotype_swatch"
        self.lithotype_input.setVisible(is_lithotype_swatch)
        self.lithotype_label_mode_input.setVisible(is_lithotype_swatch)
        self.lithotype_label.setVisible(is_lithotype_swatch)
        self.lithotype_mode_label.setVisible(is_lithotype_swatch)
        self._update_legend_manual_visibility()
        self.properties_label.setVisible(False)

    def _update_legend_manual_visibility(self) -> None:
        visible = (
            self.type_input.currentData() == "lithology_legend"
            and self.legend_scope_input.currentData() in {"manual", "used_manual"}
        )
        self.legend_manual_label.setVisible(visible)
        self.legend_manual_input.setVisible(visible)

    def _import_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self.localizer.text("masterlog_header.import_image"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.svg)",
        )
        if not filename:
            return
        try:
            source = Path(filename)
            asset = (
                create_svg_asset(source)
                if source.suffix.casefold() == ".svg"
                else create_raster_asset(source)
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
        element_type = str(self.type_input.currentData() or "text")
        text_style: dict[str, object] = {}
        if element_type in {
            "text",
            "field",
            "lithotype_swatch",
            "lithology_legend",
            "lba_legend",
        }:
            color = QColor(self.text_color_input.text().strip())
            if not color.isValid():
                raise ValueError(self.localizer.text("masterlog_header.invalid_text_color"))
            background_text = self.background_input.text().strip()
            if background_text and not QColor(background_text).isValid():
                raise ValueError(self.localizer.text("masterlog_header.invalid_color"))
            text_style = {
                "color": color.name(),
                "font_size_mm": self.font_size_input.value(),
                "bold": self.bold_input.isChecked(),
                "alignment": self.alignment_input.currentData(),
                "frame": self.frame_input.isChecked(),
            }
            if element_type in {"text", "field", "lithotype_swatch"}:
                text_style["text_orientation"] = str(
                    self.text_orientation_input.currentData() or "horizontal"
                )
                text_style["text_position"] = str(
                    self.text_position_input.currentData() or "center"
                )
            if background_text:
                text_style["background"] = QColor(background_text).name()
        if element_type == "text":
            properties: dict[str, object] = {"text": self.text_input.text(), **text_style}
        elif element_type == "field":
            field_name = self.field_input.currentData()
            properties = {"field": str(field_name), **text_style}
        elif element_type == "line":
            color = QColor(self.line_color_input.text().strip())
            if not color.isValid():
                raise ValueError(self.localizer.text("masterlog_header.invalid_color"))
            properties = {"color": color.name(), "width": self.line_width_input.value()}
        elif element_type == "image":
            asset_ref = self.image_input.currentData()
            optional_placeholder = self._original_properties.get("optional") is True
            if (not isinstance(asset_ref, str) or not asset_ref) and not optional_placeholder:
                raise ValueError(self.localizer.text("masterlog_header.select_image"))
            properties = {
                key: value
                for key, value in self._original_properties.items()
                if key
                in {
                    "optional",
                    "placeholder_text",
                    "placeholder_text_ru",
                    "placeholder_text_kk",
                    "placeholder_text_en",
                    "placeholder_font_size_mm",
                    "frame",
                    "frame_color",
                    "background",
                    "logo_role",
                }
            }
            if isinstance(asset_ref, str) and asset_ref:
                properties["asset_ref"] = asset_ref
            properties.update(
                {
                    "mode": str(self.image_mode_input.currentData() or "fit"),
                    "rotation": self.image_rotation_input.value(),
                    "opacity": self.image_opacity_input.value() / 100.0,
                }
            )
        elif element_type == "lithotype_swatch":
            lithotype_id = self.lithotype_input.currentData()
            if not isinstance(lithotype_id, str) or lithotype_id not in self.lithotypes:
                raise ValueError(
                    {
                        AppLanguage.RU: "Выберите литотип для вставки.",
                        AppLanguage.KK: "Кірістіру үшін литотипті таңдаңыз.",
                        AppLanguage.EN: "Select a lithotype to insert.",
                    }[self.localizer.language]
                )
            properties = {
                "lithotype_id": lithotype_id,
                "display_mode": str(
                    self.lithotype_label_mode_input.currentData() or "pattern_code_name"
                ),
                **text_style,
            }
        elif element_type == "lithology_legend":
            properties = {
                "scope": self.legend_scope_input.currentData(),
                "columns": self.legend_columns_input.value(),
                "show_code": self.legend_code_input.isChecked(),
                "selected_lithotype_ids": [
                    str(item.data(Qt.ItemDataRole.UserRole))
                    for item in self.legend_manual_input.selectedItems()
                ],
                **text_style,
            }
        elif element_type == "lba_legend":
            properties = text_style
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


class HeaderDataDialog(QDialog):
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
        self.language = language
        self.setWindowTitle(_TEXT[language]["data_title"])
        self.setMinimumSize(600, 480)
        self.resize(760, 680)
        self.inputs: dict[str, QLineEdit | QTextEdit] = {}
        template = controller.session.project.masterlog_templates[template_id]
        saved = controller.header_fields(template_id)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        for definition in editable_header_field_definitions():
            control: QLineEdit | QTextEdit
            if definition.multiline:
                control = QTextEdit()
                control.setMinimumHeight(72)
            else:
                control = QLineEdit()
            current = saved.get(definition.field_id, "")
            fallback = resolve_header_field(controller.session, definition.field_id, template) or ""
            if current:
                control.setText(current) if isinstance(control, QLineEdit) else control.setPlainText(current)
            elif fallback:
                control.setPlaceholderText(fallback)
            self.inputs[definition.field_id] = control
            form.addRow(definition.label(language), control)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)
        clear_button = QPushButton(_TEXT[language]["clear"])
        clear_button.clicked.connect(self._clear)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer = QHBoxLayout()
        footer.addWidget(clear_button)
        footer.addStretch(1)
        footer.addWidget(buttons)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addLayout(footer)

    def _clear(self) -> None:
        for control in self.inputs.values():
            control.clear()

    def values(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for field_name, control in self.inputs.items():
            value = control.text() if isinstance(control, QLineEdit) else control.toPlainText()
            value = value.strip()
            if value:
                result[field_name] = value
        return result


class HeaderGraphicsView(QGraphicsView):
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)


class _MovableHeaderRect(QGraphicsRectItem):
    def __init__(
        self,
        element: MasterlogHeaderElement,
        moved: Callable[[str, float, float], None],
        activated: Callable[[str], None],
    ) -> None:
        super().__init__(QRectF(0.0, 0.0, element.width_mm, element.height_mm))
        self.element_id = element.element_id
        self._moved = moved
        self._activated = activated
        self.setPos(element.x_mm, element.y_mm)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._activated(self.element_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._activated(self.element_id)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().mouseReleaseEvent(event)
        self._moved(self.element_id, self.pos().x(), self.pos().y())


class _MovableHeaderLine(QGraphicsLineItem):
    def __init__(
        self,
        element: MasterlogHeaderElement,
        moved: Callable[[str, float, float], None],
        activated: Callable[[str], None],
    ) -> None:
        super().__init__(0.0, 0.0, element.width_mm, element.height_mm)
        self.element_id = element.element_id
        self._moved = moved
        self._activated = activated
        self.setPos(element.x_mm, element.y_mm)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._activated(self.element_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._activated(self.element_id)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().mouseReleaseEvent(event)
        self._moved(self.element_id, self.pos().x(), self.pos().y())


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
        self._selected_element_id: str | None = None
        self._fit_on_refresh = True
        self.setWindowTitle(self.localizer.text("masterlog_header.title"))
        self.setMinimumSize(720, 480)
        self.resize(1120, 700)

        self.list = QListWidget()
        self.list.setMinimumWidth(260)
        self.list.itemDoubleClicked.connect(lambda _item: self._edit())
        self.list.currentItemChanged.connect(self._list_selection_changed)

        self.preview_scene = QGraphicsScene(self)
        self.preview = HeaderGraphicsView(self.preview_scene)
        self.preview.setObjectName("masterlog-header-preview")
        self.preview.setMinimumWidth(420)
        self.preview.setRenderHints(self.preview.renderHints())
        self.preview.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.preview.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.height_input = QDoubleSpinBox()
        self.height_input.setRange(10.0, 500.0)
        self.height_input.setDecimals(1)
        self.height_input.setValue(self.template.header_height_mm)
        self.height_input.editingFinished.connect(self._apply_height)
        self.snap_checkbox = QCheckBox(_TEXT[language]["snap"])
        self.snap_checkbox.setChecked(True)
        self.snap_input = QDoubleSpinBox()
        self.snap_input.setRange(0.1, 25.0)
        self.snap_input.setDecimals(1)
        self.snap_input.setValue(1.0)

        settings = QHBoxLayout()
        settings.addWidget(QLabel(_TEXT[language]["height"]))
        settings.addWidget(self.height_input)
        settings.addSpacing(16)
        settings.addWidget(self.snap_checkbox)
        settings.addWidget(QLabel(_TEXT[language]["grid"]))
        settings.addWidget(self.snap_input)
        settings.addStretch(1)
        hint = QLabel(_TEXT[language]["drag_hint"])
        hint.setWordWrap(True)
        self.page_info_label = QLabel()
        self.page_info_label.setObjectName("masterlog-header-page-info")
        self.page_info_label.setWordWrap(True)

        self.preset_button = QPushButton(
            {
                AppLanguage.RU: "Применить шаблон шапки...",
                AppLanguage.KK: "Тақырып үлгісін қолдану...",
                AppLanguage.EN: "Apply header preset...",
            }[language]
        )
        self.preset_button.clicked.connect(self._apply_preset)
        self.data_button = QPushButton(_TEXT[language]["data"])
        self.data_button.clicked.connect(self._edit_header_data)
        self.fit_button = QPushButton(_TEXT[language]["fit"])
        self.fit_button.clicked.connect(self._fit_preview)

        left_buttons = QHBoxLayout()
        left_buttons.addWidget(self.data_button)
        left_buttons.addWidget(self.preset_button)
        left_buttons.addWidget(self.fit_button)

        element_buttons = QHBoxLayout()
        for text, callback in (
            ("+", self._add),
            ({AppLanguage.RU: "Изменить", AppLanguage.KK: "Өзгерту", AppLanguage.EN: "Edit"}[language], self._edit),
            (_TEXT[language]["duplicate"], self._duplicate),
            ("↑", lambda: self._move(-1)),
            ("↓", lambda: self._move(1)),
            ("−", self._remove),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            element_buttons.addWidget(button)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addLayout(left_buttons)
        left_layout.addWidget(self.list, 1)
        left_layout.addLayout(element_buttons)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(hint)
        right_layout.addWidget(self.page_info_label)
        right_layout.addWidget(self.preview, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 760])

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        close_buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(settings)
        layout.addWidget(splitter, 1)
        layout.addWidget(close_buttons)
        self.refresh()

    @property
    def template(self):
        return self.controller.session.project.masterlog_templates[self.template_id]

    def refresh(self) -> None:
        selected = self._selected_element_id
        self.list.blockSignals(True)
        self.list.clear()
        self.preview_scene.clear()
        page_width, page_height = self._page_size_mm()
        element_right = max(
            (item.x_mm + item.width_mm for item in self.template.header_elements),
            default=0.0,
        )
        element_bottom = max(
            (item.y_mm + item.height_mm for item in self.template.header_elements),
            default=0.0,
        )
        header_width = max(page_width, element_right, 1.0)
        header_height = max(self.template.header_height_mm, element_bottom, 1.0)
        orientation = str(self.template.properties.get("orientation", "portrait"))
        orientation_text = {
            AppLanguage.RU: {"portrait": "книжная", "landscape": "альбомная"},
            AppLanguage.KK: {"portrait": "кітаптық", "landscape": "альбомдық"},
            AppLanguage.EN: {"portrait": "portrait", "landscape": "landscape"},
        }[self.localizer.language].get(orientation, orientation)
        overflow = element_right > page_width + 1e-6
        overflow_text = {
            AppLanguage.RU: " · ВНИМАНИЕ: элементы выходят за ширину страницы",
            AppLanguage.KK: " · НАЗАР: элементтер бет енінен шығып тұр",
            AppLanguage.EN: " · WARNING: elements exceed page width",
        }[self.localizer.language] if overflow else ""
        self.page_info_label.setText(
            f"{self.template.page_format} · {orientation_text} · "
            f"{page_width:g}×{page_height:g} mm{overflow_text}"
        )
        self.height_input.blockSignals(True)
        self.height_input.setValue(self.template.header_height_mm)
        self.height_input.blockSignals(False)

        self.preview_scene.addRect(
            QRectF(0.0, 0.0, page_width, header_height),
            QPen(QColor("#334155"), 0.6),
            QBrush(QColor("#ffffff")),
        )
        if header_width > page_width:
            overflow_rect = self.preview_scene.addRect(
                QRectF(page_width, 0.0, header_width - page_width, header_height),
                QPen(QColor("#dc2626"), 0.45, Qt.PenStyle.DashLine),
                QBrush(QColor(254, 226, 226, 120)),
            )
            overflow_rect.setZValue(-20)
        boundary = self.preview_scene.addLine(
            page_width, 0.0, page_width, header_height,
            QPen(QColor("#dc2626"), 0.45, Qt.PenStyle.DashLine),
        )
        boundary.setZValue(50)
        self._draw_grid(page_width, header_height)
        colors = {
            "text": QColor("#dbeafe"),
            "field": QColor("#dcfce7"),
            "image": QColor("#fef3c7"),
            "line": QColor("#e2e8f0"),
            "lithotype_swatch": QColor("#f8fafc"),
            "lithology_legend": QColor("#f3e8ff"),
            "lba_legend": QColor("#ffedd5"),
        }
        selected_row = -1
        for row, element in enumerate(self.template.header_elements):
            preview_name = self._preview_text(element).replace("\n", " ")
            if len(preview_name) > 45:
                preview_name = preview_name[:42] + "…"
            unit_mm = _TEXT[self.localizer.language]["unit_mm"]
            item = QListWidgetItem(
                f"{preview_name}\n{element.element_type} · {element.x_mm:g},{element.y_mm:g} · "
                f"{element.width_mm:g}×{element.height_mm:g} {unit_mm}"
            )
            item.setData(Qt.ItemDataRole.UserRole, element.element_id)
            self.list.addItem(item)
            if element.element_id == selected:
                selected_row = row

            if element.element_type == "line":
                line_graphic = _MovableHeaderLine(
                    element,
                    self._move_preview_element,
                    self._activate_preview_element,
                )
                line_graphic.setPen(self._line_pen(element))
                line_graphic.setToolTip(json.dumps(element.properties, ensure_ascii=False))
                self.preview_scene.addItem(line_graphic)
                continue

            rect_graphic = _MovableHeaderRect(
                element,
                self._move_preview_element,
                self._activate_preview_element,
            )
            rect_graphic.setPen(QPen(QColor("#475569"), 0.35))
            background = element.properties.get("background")
            fill = QColor(background) if isinstance(background, str) else colors[element.element_type]
            if not fill.isValid():
                fill = colors[element.element_type]
            rect_graphic.setBrush(QBrush(fill))
            rect_graphic.setToolTip(json.dumps(element.properties, ensure_ascii=False))
            self.preview_scene.addItem(rect_graphic)
            if element.element_type == "image" and self._add_image_preview(
                element, rect_graphic
            ):
                continue
            if (
                element.element_type == "lithotype_swatch"
                and self._add_lithotype_swatch_preview(element, rect_graphic)
            ):
                continue
            if (
                element.element_type == "lithology_legend"
                and self._add_lithology_legend_preview(element, rect_graphic)
            ):
                continue
            label = QGraphicsTextItem(self._preview_text(element), rect_graphic)
            color, font_size = self._text_style(element)
            label.setDefaultTextColor(color)
            font = label.font()
            font.setBold(bool(element.properties.get("bold", False)))
            label.setFont(font)
            scale = font_size / 10.0
            label.setScale(scale)
            orientation = str(element.properties.get("text_orientation", "horizontal"))
            position = str(element.properties.get("text_position", "center"))
            vertical = orientation != "horizontal"
            label.setTextWidth(
                max(1.0, (element.height_mm if vertical else element.width_mm) - 2.0)
            )
            bounds = label.boundingRect()
            if vertical:
                label.setTransformOriginPoint(bounds.center())
                label.setRotation(text_angle(orientation))
                anchor_y = element.height_mm * text_position_fraction(position)
                label.setPos(
                    element.width_mm / 2.0 - bounds.center().x() * scale,
                    anchor_y - bounds.center().y() * scale,
                )
            else:
                scaled_height = bounds.height() * scale
                y = {
                    "top": 0.3,
                    "center": max(0.3, (element.height_mm - scaled_height) / 2.0),
                    "bottom": max(0.3, element.height_mm - scaled_height - 0.3),
                }.get(position, 0.3)
                label.setPos(1.0, y)

        self.list.blockSignals(False)
        if selected_row >= 0:
            self.list.setCurrentRow(selected_row)
        self.preview_scene.setSceneRect(QRectF(-2.0, -2.0, header_width + 4.0, header_height + 4.0))
        if self._fit_on_refresh:
            self._fit_preview()
            self._fit_on_refresh = False


    def _page_size_mm(self) -> tuple[float, float]:
        dimensions = {
            "A0": (841.0, 1189.0),
            "A1": (594.0, 841.0),
            "A2": (420.0, 594.0),
            "A3": (297.0, 420.0),
            "A4": (210.0, 297.0),
            "letter": (215.9, 279.4),
            "legal": (215.9, 355.6),
        }
        if self.template.page_format == "custom":
            raw_width = self.template.properties.get("custom_width_mm", 210.0)
            raw_height = self.template.properties.get("custom_height_mm", 297.0)
            width = float(raw_width) if isinstance(raw_width, (int, float)) else 210.0
            height = float(raw_height) if isinstance(raw_height, (int, float)) else 297.0
        elif self.template.page_format == "roll":
            raw_width = self.template.properties.get("custom_width_mm", 210.0)
            width = float(raw_width) if isinstance(raw_width, (int, float)) else 210.0
            height = max(self.template.header_height_mm, 297.0)
        else:
            width, height = dimensions.get(self.template.page_format, (210.0, 297.0))
        if (
            self.template.page_format != "roll"
            and self.template.properties.get("orientation", "portrait") == "landscape"
        ):
            width, height = height, width
        return max(25.0, width), max(25.0, height)

    def _draw_grid(self, width: float, height: float) -> None:
        step = max(1.0, self.snap_input.value())
        pen = QPen(QColor("#e2e8f0"), 0.12)
        x = step
        while x < width:
            line = self.preview_scene.addLine(x, 0.0, x, height, pen)
            line.setZValue(-10)
            x += step
        y = step
        while y < height:
            line = self.preview_scene.addLine(0.0, y, width, y, pen)
            line.setZValue(-10)
            y += step

    def _fit_preview(self) -> None:
        self.preview.resetTransform()
        self.preview.fitInView(self.preview_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _apply_height(self) -> None:
        try:
            self.controller.update_header_height(self.template_id, self.height_input.value())
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self.height_input.setValue(self.template.header_height_mm)
            return
        self.refresh()

    def _edit_header_data(self) -> None:
        dialog = HeaderDataDialog(
            self.controller,
            self.template_id,
            self,
            language=self.localizer.language,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.controller.update_header_fields(self.template_id, dialog.values())
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return
        self.refresh()

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

    def _add_image_preview(
        self,
        element: MasterlogHeaderElement,
        parent: QGraphicsRectItem | None = None,
    ) -> bool:
        asset_ref = element.properties.get("asset_ref")
        asset = self.controller.session.image_assets.get(asset_ref) if isinstance(asset_ref, str) else None
        if asset is None:
            return False
        pixmap = image_asset_pixmap(asset)
        if pixmap.isNull():
            return False
        item = self.preview_scene.addPixmap(pixmap)
        mode = str(element.properties.get("mode", "fit"))
        sx = element.width_mm / max(1, pixmap.width())
        sy = element.height_mm / max(1, pixmap.height())
        if mode == "stretch":
            item.setTransform(QTransform.fromScale(sx, sy))
        else:
            scale = max(sx, sy) if mode == "fill" else min(sx, sy)
            item.setScale(scale)
        opacity = element.properties.get("opacity", 1.0)
        if isinstance(opacity, (int, float)) and not isinstance(opacity, bool):
            item.setOpacity(max(0.0, min(1.0, float(opacity))))
        rotation = element.properties.get("rotation", 0.0)
        if isinstance(rotation, (int, float)) and not isinstance(rotation, bool):
            item.setTransformOriginPoint(pixmap.width() / 2.0, pixmap.height() / 2.0)
            item.setRotation(float(rotation))
        if parent is not None:
            parent.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
            item.setParentItem(parent)
            item.setPos(0.0, 0.0)
        else:
            item.setPos(element.x_mm, element.y_mm)
        item.setToolTip(asset.original_name)
        return True

    def _add_lithology_legend_preview(
        self,
        element: MasterlogHeaderElement,
        parent: QGraphicsRectItem,
    ) -> bool:
        catalog = self._available_lithotypes()
        if not catalog:
            return False
        scope = element.properties.get("scope", "used")
        lithotype_ids: list[str]
        selected_ids = [
            str(value)
            for value in element.properties.get("selected_lithotype_ids", [])
            if isinstance(value, str)
        ]
        if scope == "all" or self.controller.session.current_well is None:
            lithotype_ids = sorted(catalog, key=lambda key: catalog[key].name_ru.casefold())
        elif scope == "manual":
            lithotype_ids = selected_ids
        else:
            seen: set[str] = set()
            lithotype_ids = []
            well = self.controller.session.current_well
            for interval in well.lithology:
                if interval.lithotype_id not in seen:
                    seen.add(interval.lithotype_id)
                    lithotype_ids.append(interval.lithotype_id)
            for sample in well.cuttings:
                for component in sample.components:
                    if component.lithotype_id not in seen:
                        seen.add(component.lithotype_id)
                        lithotype_ids.append(component.lithotype_id)
            if scope == "used_manual":
                for lithotype_id in selected_ids:
                    if lithotype_id not in seen:
                        seen.add(lithotype_id)
                        lithotype_ids.append(lithotype_id)
        lithotypes = [catalog[key] for key in lithotype_ids if key in catalog]
        if not lithotypes:
            return False
        raw_columns = element.properties.get("columns", 4)
        columns = raw_columns if isinstance(raw_columns, int) and raw_columns > 0 else 4
        columns = min(columns, max(1, len(lithotypes)))
        row_height = max(4.5, min(8.0, element.height_mm / max(1, (len(lithotypes) + columns - 1) // columns)))
        max_rows = max(1, int(element.height_mm / row_height))
        visible = lithotypes[: columns * max_rows]
        rows = max(1, (len(visible) + columns - 1) // columns)
        cell_width = element.width_mm / columns
        cell_height = element.height_mm / rows
        for index, lithotype in enumerate(visible):
            row, column = divmod(index, columns)
            x = column * cell_width
            y = row * cell_height
            swatch_width = min(6.0, max(2.5, cell_width * 0.22))
            swatch = QGraphicsRectItem(0.0, 0.0, swatch_width, max(2.0, cell_height - 0.6), parent)
            swatch.setPos(x + 0.3, y + 0.3)
            swatch.setPen(QPen(QColor("#64748b"), 0.12))
            swatch.setBrush(lithology_brush(lithotype.color, lithotype.pattern_key))
            names = {
                AppLanguage.RU: lithotype.name_ru,
                AppLanguage.KK: lithotype.name_kk or lithotype.name_ru,
                AppLanguage.EN: lithotype.name_en or lithotype.name_ru,
            }
            text = f"{lithotype.code} — {names[self.localizer.language]}"
            label = QGraphicsTextItem(text, parent)
            label.setDefaultTextColor(QColor("#0f172a"))
            label.setTextWidth(max(1.0, cell_width - swatch_width - 1.2))
            label.setScale(max(0.16, min(0.28, cell_height / 24.0)))
            label.setPos(x + swatch_width + 0.8, y)
        if len(visible) < len(lithotypes):
            parent.setToolTip(
                f"{len(visible)} / {len(lithotypes)}; увеличить область легенды для полного списка"
            )
        return True

    def _add_lithotype_swatch_preview(
        self,
        element: MasterlogHeaderElement,
        parent: QGraphicsRectItem,
    ) -> bool:
        lithotype_id = element.properties.get("lithotype_id")
        if not isinstance(lithotype_id, str):
            return False
        lithotype = self._available_lithotypes().get(lithotype_id)
        if lithotype is None:
            return False
        mode = str(element.properties.get("display_mode", "pattern_code_name"))
        if mode == "pattern_only":
            pattern_width = element.width_mm
        else:
            pattern_width = min(element.width_mm * 0.38, max(5.0, element.height_mm * 1.4))
        swatch = QGraphicsRectItem(0.0, 0.0, pattern_width, element.height_mm, parent)
        swatch.setPen(QPen(QColor("#64748b"), 0.15))
        swatch.setBrush(lithology_brush(lithotype.color, lithotype.pattern_key))
        if mode == "pattern_only":
            return True
        names = {
            AppLanguage.RU: lithotype.name_ru,
            AppLanguage.KK: lithotype.name_kk or lithotype.name_ru,
            AppLanguage.EN: lithotype.name_en or lithotype.name_ru,
        }
        text = names[self.localizer.language]
        if mode == "pattern_code_name":
            text = f"{lithotype.code} — {text}"
        label = QGraphicsTextItem(text, parent)
        color, font_size = self._text_style(element)
        label.setDefaultTextColor(color)
        font = label.font()
        font.setBold(bool(element.properties.get("bold", False)))
        label.setFont(font)
        scale = font_size / 10.0
        label.setScale(scale)
        orientation = str(element.properties.get("text_orientation", "horizontal"))
        position = str(element.properties.get("text_position", "center"))
        text_width = max(1.0, element.width_mm - pattern_width - 1.0)
        label.setTextWidth(
            max(1.0, (element.height_mm if orientation != "horizontal" else text_width) - 1.0)
        )
        bounds = label.boundingRect()
        if orientation != "horizontal":
            label.setTransformOriginPoint(bounds.center())
            label.setRotation(text_angle(orientation))
            anchor_y = element.height_mm * text_position_fraction(position)
            label.setPos(
                pattern_width + text_width / 2.0 - bounds.center().x() * scale,
                anchor_y - bounds.center().y() * scale,
            )
        else:
            scaled_height = bounds.height() * scale
            y = {
                "top": 0.3,
                "center": max(0.3, (element.height_mm - scaled_height) / 2.0),
                "bottom": max(0.3, element.height_mm - scaled_height - 0.3),
            }.get(position, 0.3)
            label.setPos(pattern_width + 0.6, y)
        return True

    def _available_lithotypes(self) -> dict[str, CatalogLithotype]:
        return {
            item.lithotype_id: item
            for item in LithotypeCatalogController(self.controller.session).available()
        }

    def _preview_text(self, element: MasterlogHeaderElement) -> str:
        if element.element_type == "text":
            value = element.properties.get("text")
            return str(value) if isinstance(value, (str, int, float)) else "text"
        if element.element_type == "field":
            field_name = element.properties.get("field")
            if not isinstance(field_name, str):
                return "{field}"
            resolved = resolve_header_field(self.controller.session, field_name, self.template)
            return resolved if resolved is not None else "{" + field_name + "}"
        if element.element_type == "image":
            asset_ref = element.properties.get("asset_ref")
            if isinstance(asset_ref, str) and asset_ref:
                asset = self.controller.session.image_assets.get(asset_ref)
                if asset is not None:
                    return asset.original_name
            key = {
                AppLanguage.RU: "placeholder_text_ru",
                AppLanguage.KK: "placeholder_text_kk",
                AppLanguage.EN: "placeholder_text_en",
            }[self.localizer.language]
            raw = element.properties.get(key) or element.properties.get("placeholder_text")
            return str(raw) if raw else {
                AppLanguage.RU: "Загрузить логотип",
                AppLanguage.KK: "Логотипті жүктеу",
                AppLanguage.EN: "Load logo",
            }[self.localizer.language]
        if element.element_type == "lithology_legend":
            return self.localizer.text("masterlog_header.lithology_legend")
        if element.element_type == "lithotype_swatch":
            lithotype_id = element.properties.get("lithotype_id")
            if isinstance(lithotype_id, str):
                lithotype = self._available_lithotypes().get(lithotype_id)
                if lithotype is not None:
                    return f"{lithotype.code} — {lithotype.localized_name(self.localizer.language.value)}"
            return {
                AppLanguage.RU: "Литотип",
                AppLanguage.KK: "Литотип",
                AppLanguage.EN: "Lithotype",
            }[self.localizer.language]
        if element.element_type == "lba_legend":
            return self.localizer.text("masterlog_header.lba_legend")
        return element.element_type

    def _selected(self) -> MasterlogHeaderElement | None:
        item = self.list.currentItem()
        if item is None:
            return None
        element_id = str(item.data(Qt.ItemDataRole.UserRole))
        return next((value for value in self.template.header_elements if value.element_id == element_id), None)

    def _activate_preview_element(self, element_id: str) -> None:
        self._selected_element_id = element_id
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == element_id:
                self.list.setCurrentRow(row)
                break

    def _list_selection_changed(self, current, _previous) -> None:
        if current is not None:
            self._selected_element_id = str(current.data(Qt.ItemDataRole.UserRole))

    def _move_preview_element(self, element_id: str, x: float, y: float) -> None:
        element = next((item for item in self.template.header_elements if item.element_id == element_id), None)
        if element is None:
            return
        if self.snap_checkbox.isChecked():
            step = self.snap_input.value()
            x = round(x / step) * step
            y = round(y / step) * step
        x = max(0.0, x)
        y = max(0.0, y)
        try:
            self.controller.update_header_element(
                self.template_id,
                element_id,
                element_type=element.element_type,
                x_mm=x,
                y_mm=y,
                width_mm=element.width_mm,
                height_mm=element.height_mm,
                properties=element.properties,
            )
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self.refresh()
            return
        self._selected_element_id = element_id
        self.refresh()

    def _add(self) -> None:
        dialog = HeaderElementDialog(
            self,
            language=self.localizer.language,
            image_assets=self.controller.session.image_assets,
            lithotypes=self._available_lithotypes(),
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
        if QMessageBox.question(self, self.windowTitle(), question) != QMessageBox.StandardButton.Yes:
            return
        preset = presets[labels.index(selected)]
        self.controller.apply_header_preset(self.template_id, preset.preset_id)
        self._fit_on_refresh = True
        self.refresh()

    def _edit(self) -> None:
        element = self._selected()
        if element:
            dialog = HeaderElementDialog(
                self,
                element=element,
                language=self.localizer.language,
                image_assets=self.controller.session.image_assets,
                lithotypes=self._available_lithotypes(),
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._apply(dialog, element.element_id)

    def _apply(self, dialog: HeaderElementDialog, element_id: str | None) -> None:
        try:
            kind, x, y, width, height, properties = dialog.values()
            if element_id is None:
                created = self.controller.add_header_element(
                    self.template_id,
                    element_type=kind,
                    x_mm=x,
                    y_mm=y,
                    width_mm=width,
                    height_mm=height,
                    properties=properties,
                )
                self._selected_element_id = created.element_id
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
                self._selected_element_id = element_id
        except (ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
        else:
            if dialog.imported_assets:
                try:
                    self.controller.install_image_assets(dialog.imported_assets)
                except (ImageAssetError, ValueError) as exc:
                    QMessageBox.warning(self, self.windowTitle(), str(exc))
        self.refresh()

    def _duplicate(self) -> None:
        element = self._selected()
        if element is None:
            return
        duplicated = self.controller.duplicate_header_element(self.template_id, element.element_id)
        self._selected_element_id = duplicated.element_id
        self.refresh()

    def _remove(self) -> None:
        element = self._selected()
        if element is None:
            return
        if QMessageBox.question(self, self.windowTitle(), _TEXT[self.localizer.language]["delete_confirm"]) != QMessageBox.StandardButton.Yes:
            return
        self.controller.remove_header_element(self.template_id, element.element_id)
        self._selected_element_id = None
        self.refresh()

    def _move(self, offset: int) -> None:
        element = self._selected()
        if element:
            self.controller.move_header_element(self.template_id, element.element_id, offset)
            self._selected_element_id = element.element_id
            self.refresh()
