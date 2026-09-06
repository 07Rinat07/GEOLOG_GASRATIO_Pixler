from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from math import isfinite
from typing import Any

from geoworkbench.domain.text_presentation import (
    normalize_text_orientation,
    normalize_text_vertical_position,
)
from geoworkbench.domain.models import (
    Dataset,
    MasterlogColumnTemplate,
    MasterlogCurveStyle,
    MasterlogHeaderElement,
    MasterlogTemplate,
    new_id,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.header_fields import header_field_defaults
from geoworkbench.printing.header_catalog import (
    HEADER_CATALOG_KIND,
    catalog_items as header_catalog_items,
    resolve_catalog_header,
)
from geoworkbench.printing.image_assets import ImageAsset, validate_image_asset
from geoworkbench.printing.masterlog_presets import builtin_form_preset, builtin_header_preset
from geoworkbench.printing.masterlog_header_forms import masterlog_header_assets
from geoworkbench.services.localization import AppLanguage


class MasterlogTemplateController:
    def __init__(self, session: ProjectSession) -> None:
        self.session = session

    def create(self, name: str) -> MasterlogTemplate:
        normalized = self._validate_unique_name(name)
        template = MasterlogTemplate(new_id(), normalized)
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.dirty = True
        return template

    def create_from_preset(
        self,
        preset_id: str,
        name: str,
        language: AppLanguage = AppLanguage.RU,
    ) -> MasterlogTemplate:
        preset = builtin_form_preset(preset_id)
        normalized = self._validate_unique_name(name)
        template = replace(
            preset.template_for(language), template_id=new_id(), name=normalized, version=1
        )
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.dirty = True
        return template

    def apply_header_preset(self, template_id: str, preset_id: str) -> MasterlogTemplate:
        template = self._require(template_id)
        preset = builtin_header_preset(preset_id)
        template.header_height_mm = preset.height_mm
        template.header_elements = list(deepcopy(preset.elements))
        template.properties["header_preset_origin"] = preset.preset_id
        current_fields = template.properties.get("header_fields")
        if not isinstance(current_fields, dict):
            current_fields = {}
        template.properties["header_fields"] = {**header_field_defaults(), **current_fields}
        self._touch(template)
        return template

    def header_catalog_items(self, language: Any = None):
        from geoworkbench.services.localization import AppLanguage

        resolved = language if isinstance(language, AppLanguage) else AppLanguage.RU
        return header_catalog_items(self.session.project.masterlog_templates, resolved)

    def create_header_template(
        self,
        name: str,
        *,
        preset_catalog_id: str | None = None,
        preferred_orientation: str = "both",
    ) -> MasterlogTemplate:
        normalized = self._validate_unique_name(name)
        if preset_catalog_id is None:
            preset_catalog_id = "factory-header:project_well"
        source = resolve_catalog_header(
            self.session.project.masterlog_templates, preset_catalog_id
        )
        template = MasterlogTemplate(
            template_id=new_id(),
            name=normalized,
            page_format="A4",
            depth_scale=source.depth_scale,
            header_height_mm=source.header_height_mm,
            header_elements=list(deepcopy(source.header_elements)),
            columns=[],
            properties={
                "catalog_kind": HEADER_CATALOG_KIND,
                "preferred_orientation": preferred_orientation,
                "header_fields": {
                    **header_field_defaults(),
                    **(
                        source.properties.get("header_fields", {})
                        if isinstance(source.properties.get("header_fields"), dict)
                        else {}
                    ),
                },
            },
        )
        self._install_default_header_assets(template)
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.dirty = True
        return template

    def save_header_to_catalog(
        self, source_template_id: str, name: str
    ) -> MasterlogTemplate:
        source = self._require(source_template_id)
        normalized = self._validate_unique_name(name)
        properties = deepcopy(source.properties)
        properties["catalog_kind"] = HEADER_CATALOG_KIND
        properties.setdefault("preferred_orientation", "both")
        template = MasterlogTemplate(
            template_id=new_id(),
            name=normalized,
            page_format=source.page_format,
            depth_scale=source.depth_scale,
            header_height_mm=source.header_height_mm,
            header_elements=list(deepcopy(source.header_elements)),
            columns=[],
            properties=properties,
            version=1,
        )
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.dirty = True
        return template

    def import_header_template(
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
        properties = deepcopy(source.properties)
        properties["catalog_kind"] = HEADER_CATALOG_KIND
        properties.setdefault("preferred_orientation", "both")
        template = MasterlogTemplate(
            template_id=new_id(),
            name=normalized,
            page_format=source.page_format,
            depth_scale=source.depth_scale,
            header_height_mm=source.header_height_mm,
            header_elements=list(deepcopy(source.header_elements)),
            columns=[],
            properties=properties,
            version=1,
        )
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.image_assets.update(image_assets)
        self.session.dirty = True
        return template

    def apply_header_catalog_item(
        self, target_template_id: str, catalog_id: str
    ) -> MasterlogTemplate:
        target = self._require(target_template_id)
        source = resolve_catalog_header(
            self.session.project.masterlog_templates, catalog_id
        )
        target.header_height_mm = source.header_height_mm
        target.header_elements = list(deepcopy(source.header_elements))
        target.properties["header_catalog_origin"] = catalog_id
        current_fields = target.properties.get("header_fields")
        source_fields = source.properties.get("header_fields")
        target.properties["header_fields"] = {
            **header_field_defaults(),
            **(source_fields if isinstance(source_fields, dict) else {}),
            **(current_fields if isinstance(current_fields, dict) else {}),
        }
        self._install_default_header_assets(target)
        self._touch(target)
        return target

    def copy_header_catalog_item(
        self, catalog_id: str, name: str
    ) -> MasterlogTemplate:
        source = resolve_catalog_header(
            self.session.project.masterlog_templates, catalog_id
        )
        normalized = self._validate_unique_name(name)
        properties = deepcopy(source.properties)
        properties["catalog_kind"] = HEADER_CATALOG_KIND
        properties.pop("factory_preset_id", None)
        template = MasterlogTemplate(
            template_id=new_id(),
            name=normalized,
            page_format=source.page_format,
            depth_scale=source.depth_scale,
            header_height_mm=source.header_height_mm,
            header_elements=list(deepcopy(source.header_elements)),
            columns=[],
            properties=properties,
            version=1,
        )
        self.session.project.masterlog_templates[template.template_id] = template
        self.session.dirty = True
        return template

    def header_fields(self, template_id: str) -> dict[str, str]:
        template = self._require(template_id)
        raw = template.properties.get("header_fields", {})
        if not isinstance(raw, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in raw.items()
            if isinstance(key, str) and isinstance(value, (str, int, float))
        }

    def update_header_fields(
        self,
        template_id: str,
        values: dict[str, str],
    ) -> dict[str, str]:
        template = self._require(template_id)
        if not isinstance(values, dict):
            raise ValueError("Данные шапки должны быть словарём")
        normalized: dict[str, str] = {}
        for key, value in values.items():
            if not isinstance(key, str) or not key.startswith("header."):
                raise ValueError(f"Некорректное поле шапки: {key!r}")
            if not isinstance(value, str):
                raise ValueError(f"Значение поля шапки {key} должно быть строкой")
            clean = value.strip()
            if len(clean) > 4000:
                raise ValueError(f"Поле шапки {key} превышает 4000 символов")
            if clean:
                normalized[key] = clean
        template.properties["header_fields"] = normalized
        self._touch(template)
        return dict(normalized)

    def update_header_height(self, template_id: str, height_mm: float) -> float:
        template = self._require(template_id)
        if (
            isinstance(height_mm, bool)
            or not isinstance(height_mm, (int, float))
            or not isfinite(height_mm)
            or not 10.0 <= float(height_mm) <= 500.0
        ):
            raise ValueError("Высота шапки должна быть от 10 до 500 мм")
        minimum = max(
            (element.y_mm + element.height_mm for element in template.header_elements),
            default=0.0,
        )
        if float(height_mm) + 1e-9 < minimum:
            raise ValueError(
                f"Высота шапки меньше нижней границы элементов ({minimum:g} мм)"
            )
        template.header_height_mm = float(height_mm)
        self._touch(template)
        return template.header_height_mm

    def fit_header_to_page(
        self,
        template_id: str,
        page_width_mm: float,
        *,
        padding_mm: float = 2.0,
    ) -> float:
        """Fit every header element into the printable page width as one composition.

        Imported SKF headers often retain a wider vendor canvas than the selected A3/A4
        page. The operation preserves relative geometry, scales text/line metrics and
        expands the declared header height to the actual lower element boundary.
        """

        template = self._require(template_id)
        values = (page_width_mm, padding_mm)
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            for value in values
        ):
            raise ValueError("Размер страницы и поля должны быть конечными числами")
        page_width = float(page_width_mm)
        padding = float(padding_mm)
        if not 25.0 <= page_width <= 5000.0:
            raise ValueError("Ширина страницы должна быть от 25 до 5000 мм")
        if not 0.0 <= padding <= min(50.0, page_width / 4.0):
            raise ValueError("Поле подгонки выходит за допустимые границы")
        if not template.header_elements:
            return 1.0

        source_left = min(element.x_mm for element in template.header_elements)
        source_right = max(
            element.x_mm + element.width_mm for element in template.header_elements
        )
        source_width = max(1.0, source_right - source_left)
        available_width = max(1.0, page_width - padding * 2.0)
        scale = min(1.0, available_width / source_width)

        metric_keys = ("font_size_mm", "placeholder_font_size_mm", "width")
        fitted: list[MasterlogHeaderElement] = []
        for element in template.header_elements:
            properties = deepcopy(element.properties)
            for key in metric_keys:
                value = properties.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    properties[key] = max(0.1, float(value) * scale)
            fitted.append(
                self._validated_header_element(
                    element.element_id,
                    element.element_type,
                    padding + (element.x_mm - source_left) * scale,
                    max(0.0, element.y_mm * scale),
                    max(0.1, element.width_mm * scale),
                    max(0.1, element.height_mm * scale),
                    properties,
                )
            )

        template.header_elements = fitted
        lower_boundary = max(
            element.y_mm + element.height_mm for element in template.header_elements
        )
        template.header_height_mm = min(500.0, max(10.0, lower_boundary + padding))
        self._touch(template)
        return scale

    def duplicate_header_element(
        self, template_id: str, element_id: str
    ) -> MasterlogHeaderElement:
        template = self._require(template_id)
        source = template.header_elements[self._header_index(template, element_id)]
        clone = deepcopy(source)
        clone.element_id = new_id()
        clone.x_mm += 2.0
        clone.y_mm += 2.0
        template.header_elements.append(clone)
        self._touch(template)
        return clone

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
        formats = {
            "a0": "A0", "a1": "A1", "a2": "A2", "a3": "A3", "a4": "A4",
            "letter": "letter", "legal": "legal", "custom": "custom", "roll": "roll",
        }
        try:
            normalized_format = formats[page_format.strip().casefold()]
        except KeyError as exc:
            raise ValueError("Формат masterlog должен быть A0–A4, Letter, Legal, custom или roll") from exc
        if isinstance(depth_scale, bool) or not isinstance(depth_scale, int):
            raise ValueError("Масштаб masterlog должен быть целым числом")
        if not 10 <= depth_scale <= 10000:
            raise ValueError("Масштаб masterlog должен быть от 1:10 до 1:10000")
        dimensions = (header_height_mm, custom_width_mm, custom_height_mm)
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)
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
        if normalized_format == "roll":
            normalized_orientation = "portrait"
        dimensions_mm: dict[str, tuple[float, float]] = {
            "A0": (841.0, 1189.0), "A1": (594.0, 841.0),
            "A2": (420.0, 594.0), "A3": (297.0, 420.0),
            "A4": (210.0, 297.0), "letter": (215.9, 279.4),
            "legal": (215.9, 355.6), "custom": (custom_width_mm, custom_height_mm),
        }
        page_dimensions = dimensions_mm.get(normalized_format)
        page_height = None if page_dimensions is None else (
            page_dimensions[1]
            if normalized_orientation == "portrait"
            else page_dimensions[0]
        )
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
        if any(
            item.object_type == "masterlog_symbol"
            and item.properties.get("template_id") == template_id
            for well in self.session.project.wells.values()
            for item in well.canvas_objects
        ):
            raise ValueError(
                "Форма masterlog используется глубинными обозначениями; сначала удалите их"
            )
        del self.session.project.masterlog_templates[template_id]
        self.session.dirty = True
        return template

    def required_curve_mnemonics(self, template_id: str) -> tuple[str, ...]:
        template = self._require(template_id)
        return tuple(
            dict.fromkeys(
                mnemonic
                for column in template.columns
                if column.column_type == "curves"
                for mnemonic in column.curve_mnemonics
            )
        )

    def curve_bindings(self, template_id: str, dataset: Dataset) -> dict[str, str]:
        template = self._require(template_id)
        raw_profiles = template.properties.get("dataset_curve_bindings", {})
        if not isinstance(raw_profiles, dict):
            return {}
        raw = raw_profiles.get(dataset.dataset_id, {})
        if not isinstance(raw, dict):
            return {}
        return {
            str(mnemonic): str(curve_id)
            for mnemonic, curve_id in raw.items()
            if isinstance(mnemonic, str)
            and isinstance(curve_id, str)
            and curve_id in dataset.curves
        }

    def save_curve_bindings(
        self, template_id: str, dataset: Dataset, bindings: dict[str, str]
    ) -> dict[str, str]:
        template = self._require(template_id)
        required = self.required_curve_mnemonics(template_id)
        missing = [mnemonic for mnemonic in required if mnemonic not in bindings]
        extra = sorted(set(bindings) - set(required))
        unknown = sorted(
            curve_id for curve_id in bindings.values() if curve_id not in dataset.curves
        )
        if missing:
            raise ValueError("Не сопоставлены параметры формы: " + ", ".join(missing))
        if extra:
            raise ValueError("Лишние параметры сопоставления: " + ", ".join(extra))
        if unknown:
            raise ValueError("Кривые dataset не найдены: " + ", ".join(unknown))
        normalized = {mnemonic: bindings[mnemonic] for mnemonic in required}
        raw_profiles = template.properties.setdefault("dataset_curve_bindings", {})
        if not isinstance(raw_profiles, dict):
            raise ValueError("Сохранённые сопоставления формы повреждены")
        raw_profiles[dataset.dataset_id] = normalized
        self._touch(template)
        return normalized

    def delete_curve_bindings(self, template_id: str, dataset_id: str) -> None:
        template = self._require(template_id)
        raw_profiles = template.properties.get("dataset_curve_bindings")
        if not isinstance(raw_profiles, dict) or dataset_id not in raw_profiles:
            raise KeyError("Сопоставление параметров для dataset не найдено")
        del raw_profiles[dataset_id]
        self._touch(template)

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
        curve_styles: dict[str, MasterlogCurveStyle] | None = None,
        grid_x: bool = False,
        grid_y: bool = False,
        grid_major_divisions: int = 5,
        grid_minor_divisions: int = 5,
        grid_alpha: float = 0.2,
        grid_print: bool = True,
        title_orientation: str = "horizontal",
        title_position: str = "center",
    ) -> MasterlogColumnTemplate:
        template = self._require(template_id)
        column = self._validated_column(
            new_id(),
            title,
            column_type,
            width_mm,
            curve_mnemonics or [],
            x_scale,
            x_min,
            x_max,
            show_legend,
            line_color,
            line_width,
            line_style,
            curve_styles or {},
            grid_x,
            grid_y,
            grid_major_divisions,
            grid_minor_divisions,
            grid_alpha,
            grid_print,
            title_orientation,
            title_position,
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
        curve_styles: dict[str, MasterlogCurveStyle] | None = None,
        grid_x: bool | None = None,
        grid_y: bool | None = None,
        grid_major_divisions: int | None = None,
        grid_minor_divisions: int | None = None,
        grid_alpha: float | None = None,
        grid_print: bool | None = None,
        title_orientation: str | None = None,
        title_position: str | None = None,
    ) -> MasterlogColumnTemplate:
        template = self._require(template_id)
        existing = template.columns[self._column_index(template, column_id)]
        column = self._validated_column(
            column_id,
            title,
            column_type,
            width_mm,
            curve_mnemonics,
            x_scale,
            x_min,
            x_max,
            show_legend,
            line_color,
            line_width,
            line_style,
            existing.curve_styles if curve_styles is None else curve_styles,
            existing.grid_x if grid_x is None else grid_x,
            existing.grid_y if grid_y is None else grid_y,
            existing.grid_major_divisions if grid_major_divisions is None else grid_major_divisions,
            existing.grid_minor_divisions if grid_minor_divisions is None else grid_minor_divisions,
            existing.grid_alpha if grid_alpha is None else grid_alpha,
            existing.grid_print if grid_print is None else grid_print,
            str(existing.properties.get("title_orientation", "horizontal"))
            if title_orientation is None
            else title_orientation,
            str(existing.properties.get("title_position", "center"))
            if title_position is None
            else title_position,
        )
        column.properties.update(deepcopy(existing.properties))
        column.properties["title_orientation"] = normalize_text_orientation(
            title_orientation
            if title_orientation is not None
            else str(existing.properties.get("title_orientation", "horizontal"))
        )
        column.properties["title_position"] = normalize_text_vertical_position(
            title_position
            if title_position is not None
            else str(existing.properties.get("title_position", "center"))
        )
        index = self._column_index(template, column_id)
        template.columns[index] = column
        self._touch(template)
        return column

    def remove_column(self, template_id: str, column_id: str) -> MasterlogColumnTemplate:
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
            new_id(),
            element_type,
            x_mm,
            y_mm,
            width_mm,
            height_mm,
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

    def remove_header_element(self, template_id: str, element_id: str) -> MasterlogHeaderElement:
        template = self._require(template_id)
        element = template.header_elements.pop(self._header_index(template, element_id))
        self._touch(template)
        return element

    def move_header_element(self, template_id: str, element_id: str, offset: int) -> bool:
        template = self._require(template_id)
        index = self._header_index(template, element_id)
        target = max(0, min(index + offset, len(template.header_elements) - 1))
        if target == index:
            return False
        template.header_elements.insert(target, template.header_elements.pop(index))
        self._touch(template)
        return True

    def image_asset_references(self, asset_id: str) -> tuple[str, ...]:
        references = {
            template.name
            for template in self.session.project.masterlog_templates.values()
            if any(
                element.element_type == "image" and element.properties.get("asset_ref") == asset_id
                for element in template.header_elements
            )
        }
        template_names = {
            template_id: template.name
            for template_id, template in self.session.project.masterlog_templates.items()
        }
        for well in self.session.project.wells.values():
            if well.passport is not None and asset_id in well.passport.logo_refs.values():
                references.add(well.name)
            for item in well.canvas_objects:
                if (
                    item.object_type == "masterlog_symbol"
                    and item.properties.get("asset_ref") == asset_id
                ):
                    template_id = item.properties.get("template_id")
                    references.add(template_names.get(str(template_id), well.name))
        return tuple(sorted(references))

    def remove_image_asset(self, asset_id: str) -> ImageAsset:
        references = self.image_asset_references(asset_id)
        if references:
            raise ValueError("Image asset используется в шаблонах: " + ", ".join(references))
        try:
            asset = self.session.image_assets.pop(asset_id)
        except KeyError as exc:
            raise KeyError(f"Image asset не найден: {asset_id}") from exc
        self.session.dirty = True
        return asset

    def install_image_assets(
        self, assets: dict[str, ImageAsset]
    ) -> tuple[ImageAsset, ...]:
        """Validate and install a batch of image assets through one controller call."""

        pending: list[ImageAsset] = []
        resolved: list[ImageAsset] = []
        for asset_id, asset in assets.items():
            if asset_id != asset.asset_id:
                raise ValueError(f"ID image asset не совпадает с ключом: {asset_id}")
            validate_image_asset(asset.asset_id, asset)
            existing = self.session.image_assets.get(asset.asset_id)
            if existing is not None:
                if existing.payload != asset.payload or existing.media_type != asset.media_type:
                    raise ValueError(f"Конфликт содержимого image asset: {asset.asset_id}")
                resolved.append(existing)
            else:
                pending.append(asset)
                resolved.append(asset)
        for asset in pending:
            self.session.image_assets[asset.asset_id] = asset
        if pending:
            self.session.dirty = True
        return tuple(resolved)

    def install_image_asset(self, asset: ImageAsset) -> ImageAsset:
        validate_image_asset(asset.asset_id, asset)
        existing = self.session.image_assets.get(asset.asset_id)
        if existing is not None:
            if existing.payload != asset.payload or existing.media_type != asset.media_type:
                raise ValueError(f"Конфликт содержимого image asset: {asset.asset_id}")
            return existing
        self.session.image_assets[asset.asset_id] = asset
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
        supported_types = {
            "text",
            "field",
            "image",
            "line",
            "lithotype_swatch",
            "lithology_legend",
            "lba_legend",
        }
        if not element_id or normalized_type not in supported_types:
            raise ValueError(
                "Тип элемента шапки должен быть text, field, image, line, "
                "lithotype_swatch, lithology_legend или lba_legend"
            )
        values = (x_mm, y_mm, width_mm, height_mm)
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)
            for value in values
        ):
            raise ValueError("Геометрия элемента шапки должна состоять из конечных чисел")
        if x_mm < 0 or y_mm < 0 or not 0.1 <= width_mm <= 5000 or not 0.1 <= height_mm <= 5000:
            raise ValueError("Координаты должны быть неотрицательными, размеры — 0.1–5000 мм")
        if not isinstance(properties, dict):
            raise ValueError("Свойства элемента шапки должны быть объектом")
        return MasterlogHeaderElement(
            element_id,
            normalized_type,
            float(x_mm),
            float(y_mm),
            float(width_mm),
            float(height_mm),
            deepcopy(properties),
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
        curve_styles: dict[str, MasterlogCurveStyle],
        grid_x: bool,
        grid_y: bool,
        grid_major_divisions: int,
        grid_minor_divisions: int,
        grid_alpha: float,
        grid_print: bool,
        title_orientation: str,
        title_position: str,
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
        normalized_styles = {
            mnemonic: style for mnemonic, style in curve_styles.items() if mnemonic in mnemonics
        }
        if not all(isinstance(style, MasterlogCurveStyle) for style in normalized_styles.values()):
            raise ValueError("Настройки кривых должны использовать MasterlogCurveStyle")
        if x_scale == "logarithmic" and any(
            style.x_min is not None and style.x_min <= 0 for style in normalized_styles.values()
        ):
            raise ValueError("Логарифмический диапазон кривой должен быть положительным")
        column = MasterlogColumnTemplate(
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
            curve_styles=normalized_styles,
            grid_x=grid_x,
            grid_y=grid_y,
            grid_major_divisions=grid_major_divisions,
            grid_minor_divisions=grid_minor_divisions,
            grid_alpha=grid_alpha,
            grid_print=grid_print,
        )
        column.properties["title_orientation"] = normalize_text_orientation(
            title_orientation
        )
        column.properties["title_position"] = normalize_text_vertical_position(
            title_position
        )
        return column

    def _touch(self, template: MasterlogTemplate) -> None:
        template.version += 1
        self.session.dirty = True

    def _install_default_header_assets(self, template: MasterlogTemplate) -> None:
        """Make factory logos/symbols available to the editable header preview."""
        refs = {
            element.properties.get("asset_ref")
            for element in template.header_elements
            if isinstance(element.properties.get("asset_ref"), str)
        }
        for asset in masterlog_header_assets().values():
            if asset.asset_id in refs and asset.asset_id not in self.session.image_assets:
                self.session.image_assets[asset.asset_id] = asset

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
            template_id != exclude_id and template.name.casefold() == normalized.casefold()
            for template_id, template in self.session.project.masterlog_templates.items()
        )
        if duplicate:
            raise ValueError(f"Шаблон мастерлога уже существует: {normalized}")
        return normalized
