from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from math import isfinite
from typing import Any

from geoworkbench.domain.models import (
    MasterlogColumnTemplate,
    MasterlogHeaderElement,
    MasterlogTemplate,
    new_id,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.image_assets import ImageAsset


class MasterlogTemplateController:
    def __init__(self, session: ProjectSession) -> None:
        self.session = session

    def create(self, name: str) -> MasterlogTemplate:
        normalized = self._validate_unique_name(name)
        template = MasterlogTemplate(new_id(), normalized)
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.dirty = True
        return template

    def copy(self, template_id: str, name: str) -> MasterlogTemplate:
        source = self._require(template_id)
        normalized = self._validate_unique_name(name)
        template = replace(
            deepcopy(source),
            template_id=new_id(),
            name=normalized,
            version=1,
        )
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.dirty = True
        return template

    def import_template(
        self,
        source: MasterlogTemplate,
        image_assets: dict[str, ImageAsset],
        name: str,
    ) -> MasterlogTemplate:
        normalized = self._validate_unique_name(name)
        for asset_id, asset in image_assets.items():
            existing = self.session.image_assets.get(asset_id)
            if existing is not None and existing.payload != asset.payload:
                raise ValueError(f"Конфликт содержимого image asset: {asset_id}")
        template = replace(
            deepcopy(source),
            template_id=new_id(),
            name=normalized,
            version=1,
        )
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.image_assets.update(image_assets)
        self.session.dirty = True
        return template

    def rename(self, template_id: str, name: str) -> MasterlogTemplate:
        template = self._require(template_id)
        normalized = self._validate_unique_name(name, exclude_id=template_id)
        template.name = normalized
        template.version += 1
        self.session.dirty = True
        return template

    def configure_page(
        self,
        template_id: str,
        *,
        page_format: str,
        depth_scale: int,
        header_height_mm: float,
        custom_width_mm: float = 210.0,
        custom_height_mm: float = 297.0,
        orientation: str = "portrait",
    ) -> MasterlogTemplate:
        template = self._require(template_id)
        formats = {"a4": "A4", "a3": "A3", "custom": "custom", "roll": "roll"}
        try:
            normalized_format = formats[page_format.strip().casefold()]
        except KeyError as exc:
            raise ValueError("Формат masterlog должен быть A4, A3, custom или roll") from exc
        if isinstance(depth_scale, bool) or not isinstance(depth_scale, int):
            raise ValueError("Масштаб masterlog должен быть целым числом")
        if not 10 <= depth_scale <= 10000:
            raise ValueError("Масштаб masterlog должен быть от 1:10 до 1:10000")
        dimensions = (header_height_mm, custom_width_mm, custom_height_mm)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            for value in dimensions
        ):
            raise ValueError("Размеры masterlog должны быть конечными числами")
        if not 5.0 <= header_height_mm <= 500.0:
            raise ValueError("Высота шапки masterlog должна быть от 5 до 500 мм")
        if not 25.0 <= custom_width_mm <= 5000.0 or not 25.0 <= custom_height_mm <= 5000.0:
            raise ValueError("Пользовательский лист должен быть от 25 до 5000 мм")
        normalized_orientation = orientation.strip().casefold()
        if normalized_orientation not in {"portrait", "landscape"}:
            raise ValueError("Ориентация masterlog должна быть portrait или landscape")
        page_height = {
            ("A4", "portrait"): 297.0,
            ("A4", "landscape"): 210.0,
            ("A3", "portrait"): 420.0,
            ("A3", "landscape"): 297.0,
            ("custom", "portrait"): custom_height_mm,
            ("custom", "landscape"): custom_width_mm,
        }.get((normalized_format, normalized_orientation))
        if page_height is not None and header_height_mm + 12.0 >= page_height:
            raise ValueError("Высота шапки не оставляет места для глубинных колонок")
        template.page_format = normalized_format
        template.depth_scale = depth_scale
        template.header_height_mm = float(header_height_mm)
        template.properties["custom_width_mm"] = float(custom_width_mm)
        template.properties["custom_height_mm"] = float(custom_height_mm)
        template.properties["orientation"] = normalized_orientation
        self._touch(template)
        return template

    def delete(self, template_id: str) -> MasterlogTemplate:
        template = self._require(template_id)
        del self.session.project.masterlog_templates[template_id]
        self.session.dirty = True
        return template

    def add_column(
        self,
        template_id: str,
        *,
        title: str,
        column_type: str,
        width_mm: float,
        curve_mnemonics: list[str] | None = None,
        x_scale: str = "linear",
        x_min: float | None = None,
        x_max: float | None = None,
        show_legend: bool = True,
        line_color: str = "#2563eb",
        line_width: float = 1.5,
        line_style: str = "solid",
    ) -> MasterlogColumnTemplate:
        template = self._require(template_id)
        column = self._validated_column(
            new_id(), title, column_type, width_mm, curve_mnemonics or [],
            x_scale, x_min, x_max, show_legend,
            line_color, line_width, line_style,
        )
        template.columns.append(column)
        self._touch(template)
        return column

    def update_column(
        self,
        template_id: str,
        column_id: str,
        *,
        title: str,
        column_type: str,
        width_mm: float,
        curve_mnemonics: list[str],
        x_scale: str = "linear",
        x_min: float | None = None,
        x_max: float | None = None,
        show_legend: bool = True,
        line_color: str = "#2563eb",
        line_width: float = 1.5,
        line_style: str = "solid",
    ) -> MasterlogColumnTemplate:
        template = self._require(template_id)
        column = self._validated_column(
            column_id, title, column_type, width_mm, curve_mnemonics,
            x_scale, x_min, x_max, show_legend,
            line_color, line_width, line_style,
        )
        index = self._column_index(template, column_id)
        template.columns[index] = column
        self._touch(template)
        return column

    def remove_column(
        self, template_id: str, column_id: str
    ) -> MasterlogColumnTemplate:
        template = self._require(template_id)
        index = self._column_index(template, column_id)
        column = template.columns.pop(index)
        self._touch(template)
        return column

    def move_column(self, template_id: str, column_id: str, offset: int) -> bool:
        template = self._require(template_id)
        index = self._column_index(template, column_id)
        target = max(0, min(index + offset, len(template.columns) - 1))
        if target == index:
            return False
        template.columns.insert(target, template.columns.pop(index))
        self._touch(template)
        return True

    def add_header_element(
        self,
        template_id: str,
        *,
        element_type: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        properties: dict[str, Any] | None = None,
    ) -> MasterlogHeaderElement:
        template = self._require(template_id)
        element = self._validated_header_element(
            new_id(), element_type, x_mm, y_mm, width_mm, height_mm,
            properties or {},
        )
        template.header_elements.append(element)
        self._touch(template)
        return element

    def update_header_element(
        self,
        template_id: str,
        element_id: str,
        *,
        element_type: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        properties: dict[str, Any],
    ) -> MasterlogHeaderElement:
        template = self._require(template_id)
        index = self._header_index(template, element_id)
        element = self._validated_header_element(
            element_id, element_type, x_mm, y_mm, width_mm, height_mm, properties
        )
        template.header_elements[index] = element
        self._touch(template)
        return element

    def remove_header_element(
        self, template_id: str, element_id: str
    ) -> MasterlogHeaderElement:
        template = self._require(template_id)
        element = template.header_elements.pop(self._header_index(template, element_id))
        self._touch(template)
        return element

    def move_header_element(
        self, template_id: str, element_id: str, offset: int
    ) -> bool:
        template = self._require(template_id)
        index = self._header_index(template, element_id)
        target = max(0, min(index + offset, len(template.header_elements) - 1))
        if target == index:
            return False
        template.header_elements.insert(target, template.header_elements.pop(index))
        self._touch(template)
        return True

    def image_asset_references(self, asset_id: str) -> tuple[str, ...]:
        return tuple(
            template.name
            for template in self.session.project.masterlog_templates.values()
            if any(
                element.element_type == "image"
                and element.properties.get("asset_ref") == asset_id
                for element in template.header_elements
            )
        )

    def remove_image_asset(self, asset_id: str) -> ImageAsset:
        references = self.image_asset_references(asset_id)
        if references:
            raise ValueError(
                "Image asset используется в шаблонах: " + ", ".join(references)
            )
        try:
            asset = self.session.image_assets.pop(asset_id)
        except KeyError as exc:
            raise KeyError(f"Image asset не найден: {asset_id}") from exc
        self.session.dirty = True
        return asset

    def rename_image_asset(self, asset_id: str, name: str) -> ImageAsset:
        normalized = name.strip()
        if (
            not normalized
            or len(normalized) > 255
            or "/" in normalized
            or "\\" in normalized
            or any(ord(character) < 32 for character in normalized)
        ):
            raise ValueError(
                "Имя image asset должно содержать 1–255 символов без путей и управляющих символов"
            )
        try:
            asset = self.session.image_assets[asset_id]
        except KeyError as exc:
            raise KeyError(f"Image asset не найден: {asset_id}") from exc
        renamed = replace(asset, original_name=normalized)
        self.session.image_assets[asset_id] = renamed
        self.session.dirty = True
        return renamed

    @staticmethod
    def _header_index(template: MasterlogTemplate, element_id: str) -> int:
        for index, element in enumerate(template.header_elements):
            if element.element_id == element_id:
                return index
        raise KeyError(f"Элемент шапки мастерлога не найден: {element_id}")

    @staticmethod
    def _validated_header_element(
        element_id: str,
        element_type: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        properties: dict[str, Any],
    ) -> MasterlogHeaderElement:
        normalized_type = element_type.strip()
        if not element_id or normalized_type not in {"text", "field", "image", "line"}:
            raise ValueError("Тип элемента шапки должен быть text, field, image или line")
        values = (x_mm, y_mm, width_mm, height_mm)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            for value in values
        ):
            raise ValueError("Геометрия элемента шапки должна состоять из конечных чисел")
        if x_mm < 0 or y_mm < 0 or not 0.1 <= width_mm <= 5000 or not 0.1 <= height_mm <= 5000:
            raise ValueError("Координаты должны быть неотрицательными, размеры — 0.1–5000 мм")
        if not isinstance(properties, dict):
            raise ValueError("Свойства элемента шапки должны быть объектом")
        return MasterlogHeaderElement(
            element_id, normalized_type, float(x_mm), float(y_mm),
            float(width_mm), float(height_mm), deepcopy(properties),
        )

    def _column_index(self, template: MasterlogTemplate, column_id: str) -> int:
        for index, column in enumerate(template.columns):
            if column.column_id == column_id:
                return index
        raise KeyError(f"Колонка мастерлога не найдена: {column_id}")

    @staticmethod
    def _validated_column(
        column_id: str,
        title: str,
        column_type: str,
        width_mm: float,
        curve_mnemonics: list[str],
        x_scale: str,
        x_min: float | None,
        x_max: float | None,
        show_legend: bool,
        line_color: str,
        line_width: float,
        line_style: str,
    ) -> MasterlogColumnTemplate:
        normalized_title = title.strip()
        normalized_type = column_type.strip()
        mnemonics = list(dict.fromkeys(value.strip() for value in curve_mnemonics))
        if not column_id or not normalized_title or not normalized_type:
            raise ValueError("ID, название и тип колонки не могут быть пустыми")
        if isinstance(width_mm, bool) or not isinstance(width_mm, (int, float)):
            raise ValueError("Ширина колонки должна быть числом")
        if not 5.0 <= width_mm <= 200.0:
            raise ValueError("Ширина колонки должна быть от 5 до 200 мм")
        if any(not mnemonic for mnemonic in mnemonics):
            raise ValueError("Мнемоники кривых не могут быть пустыми")
        return MasterlogColumnTemplate(
            column_id,
            normalized_title,
            normalized_type,
            float(width_mm),
            mnemonics,
            x_scale=x_scale,
            x_min=x_min,
            x_max=x_max,
            show_legend=show_legend,
            line_color=line_color.strip(),
            line_width=line_width,
            line_style=line_style,
        )

    def _touch(self, template: MasterlogTemplate) -> None:
        template.version += 1
        self.session.dirty = True

    def _require(self, template_id: str) -> MasterlogTemplate:
        try:
            return self.session.project.masterlog_templates[template_id]
        except KeyError as exc:
            raise KeyError(f"Шаблон мастерлога не найден: {template_id}") from exc

    def _validate_unique_name(self, name: str, *, exclude_id: str | None = None) -> str:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Имя шаблона мастерлога не может быть пустым")
        if len(normalized) > 200:
            raise ValueError("Имя шаблона мастерлога не должно превышать 200 символов")
        duplicate = any(
            template_id != exclude_id
            and template.name.casefold() == normalized.casefold()
            for template_id, template in self.session.project.masterlog_templates.items()
        )
        if duplicate:
            raise ValueError(f"Шаблон мастерлога уже существует: {normalized}")
        return normalized
