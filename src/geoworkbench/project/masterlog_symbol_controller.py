from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import isfinite

import numpy as np

from geoworkbench.domain.models import CanvasObject, MasterlogTemplate, Well, new_id
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.canvas_history import CanvasObjectHistory
from geoworkbench.services.time_depth_mapping import resolve_time_to_depth


MASTERLOG_SYMBOL_TYPE = "masterlog_symbol"


@dataclass(frozen=True, slots=True)
class PlacedMasterlogSymbol:
    object_id: str
    anchor_type: str
    top_depth: float
    bottom_depth: float
    column_id: str
    asset_ref: str
    width_mm: float
    height_mm: float
    label: str
    parameter_mnemonic: str | None
    time_value: str | None

    @property
    def depth(self) -> float:
        return self.top_depth


@dataclass(slots=True)
class MasterlogSymbolController:
    session: ProjectSession
    history: CanvasObjectHistory = field(default_factory=CanvasObjectHistory)

    def available(self, template_id: str) -> tuple[PlacedMasterlogSymbol, ...]:
        self._require_template(template_id)
        result = [
            self._to_symbol(item)
            for item in self._require_well().canvas_objects
            if item.object_type == MASTERLOG_SYMBOL_TYPE
            and item.properties.get("template_id") == template_id
        ]
        return tuple(sorted(result, key=lambda item: (item.top_depth, item.object_id)))

    def add(
        self,
        template_id: str,
        *,
        depth: float,
        column_id: str,
        asset_ref: str,
        width_mm: float,
        height_mm: float,
        label: str = "",
        anchor_type: str = "depth",
        bottom_depth: float | None = None,
        parameter_mnemonic: str | None = None,
        time_value: str | None = None,
    ) -> PlacedMasterlogSymbol:
        values = self._validate(
            template_id,
            anchor_type,
            depth,
            bottom_depth,
            column_id,
            asset_ref,
            width_mm,
            height_mm,
            label,
            parameter_mnemonic,
            time_value,
        )
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        (
            normalized_anchor,
            normalized_top,
            normalized_bottom,
            normalized_width,
            normalized_height,
            normalized_label,
            normalized_parameter,
            normalized_time,
        ) = values
        item = CanvasObject(
            new_id(),
            MASTERLOG_SYMBOL_TYPE,
            normalized_anchor,
            0.0,
            normalized_top,
            normalized_width,
            normalized_height,
            top_depth=normalized_top,
            bottom_depth=normalized_bottom,
            track_id=column_id,
            parameter_mnemonic=normalized_parameter,
            time_value=normalized_time,
            properties={
                "template_id": template_id,
                "asset_ref": asset_ref,
                "label": normalized_label,
            },
        )
        well.canvas_objects.append(item)
        self.history.record(well, before, description="Добавление обозначения masterlog")
        self.session.dirty = True
        return self._to_symbol(item)

    def update(
        self,
        object_id: str,
        *,
        template_id: str,
        depth: float,
        column_id: str,
        asset_ref: str,
        width_mm: float,
        height_mm: float,
        label: str = "",
        anchor_type: str = "depth",
        bottom_depth: float | None = None,
        parameter_mnemonic: str | None = None,
        time_value: str | None = None,
    ) -> PlacedMasterlogSymbol:
        values = self._validate(
            template_id,
            anchor_type,
            depth,
            bottom_depth,
            column_id,
            asset_ref,
            width_mm,
            height_mm,
            label,
            parameter_mnemonic,
            time_value,
        )
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        item = self._require_item(object_id, template_id)
        (
            normalized_anchor,
            normalized_top,
            normalized_bottom,
            normalized_width,
            normalized_height,
            normalized_label,
            normalized_parameter,
            normalized_time,
        ) = values
        item.anchor_type = normalized_anchor
        item.y = normalized_top
        item.top_depth = normalized_top
        item.bottom_depth = normalized_bottom
        item.track_id = column_id
        item.parameter_mnemonic = normalized_parameter
        item.time_value = normalized_time
        item.width = normalized_width
        item.height = normalized_height
        item.properties.update(asset_ref=asset_ref, label=normalized_label)
        self.history.record(well, before, description="Изменение обозначения masterlog")
        self.session.dirty = True
        return self._to_symbol(item)

    def remove(self, object_id: str, template_id: str) -> PlacedMasterlogSymbol:
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        item = self._require_item(object_id, template_id)
        result = self._to_symbol(item)
        well.canvas_objects.remove(item)
        self.history.record(well, before, description="Удаление обозначения masterlog")
        self.session.dirty = True
        return result

    def undo(self) -> str:
        command = self.history.undo()
        self.session.dirty = True
        return command.description

    def redo(self) -> str:
        command = self.history.redo()
        self.session.dirty = True
        return command.description

    def _validate(
        self,
        template_id: str,
        anchor_type: str,
        top_depth: float,
        bottom_depth: float | None,
        column_id: str,
        asset_ref: str,
        width_mm: float,
        height_mm: float,
        label: str,
        parameter_mnemonic: str | None,
        time_value: str | None,
    ) -> tuple[str, float, float, float, float, str, str | None, str | None]:
        template = self._require_template(template_id)
        column = next((item for item in template.columns if item.column_id == column_id), None)
        if column is None:
            raise ValueError("Колонка обозначения отсутствует в форме masterlog")
        if asset_ref not in self.session.image_assets:
            raise ValueError("Графический ресурс обозначения отсутствует в проекте")
        normalized_anchor = anchor_type.strip().casefold()
        if normalized_anchor not in {"depth", "interval", "parameter", "time"}:
            raise ValueError("Привязка обозначения должна быть depth, interval, parameter или time")
        normalized_time: str | None = None
        dataset = self.session.current_dataset
        if normalized_anchor == "time":
            if dataset is None:
                raise ValueError("Для временной привязки требуется dataset")
            normalized_time = (time_value or "").strip()
            top_depth = resolve_time_to_depth(dataset, normalized_time).depth
        effective_bottom = top_depth if normalized_anchor != "interval" else bottom_depth
        numbers = (top_depth, effective_bottom, width_mm, height_mm)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in numbers):
            raise ValueError("Глубина и размеры обозначения должны быть числами")
        if effective_bottom is None:
            raise ValueError("Для интервального обозначения требуется низ интервала")
        normalized_top = float(top_depth)
        normalized_bottom = float(effective_bottom)
        normalized_width = float(width_mm)
        normalized_height = float(height_mm)
        if not all(
            isfinite(value)
            for value in (normalized_top, normalized_bottom, normalized_width, normalized_height)
        ):
            raise ValueError("Глубина и размеры обозначения должны быть конечными")
        if normalized_anchor == "interval" and normalized_bottom <= normalized_top:
            raise ValueError("Низ интервала должен быть больше верха")
        if not 1.0 <= normalized_width <= 50.0 or not 1.0 <= normalized_height <= 50.0:
            raise ValueError("Размер обозначения должен быть от 1 до 50 мм")
        if dataset is not None:
            finite_depth = dataset.depth[np.isfinite(dataset.depth)]
            if finite_depth.size and not (
                float(np.min(finite_depth)) <= normalized_top
                and normalized_bottom <= float(np.max(finite_depth))
            ):
                raise ValueError("Глубина обозначения находится вне текущего набора данных")
        normalized_label = label.strip()
        if len(normalized_label) > 200:
            raise ValueError("Подпись обозначения не должна превышать 200 символов")
        normalized_parameter: str | None = None
        if normalized_anchor == "parameter":
            normalized_parameter = (parameter_mnemonic or "").strip()
            if not normalized_parameter or normalized_parameter not in column.curve_mnemonics:
                raise ValueError("Параметр обозначения должен входить в выбранную колонку")
            if dataset is None or dataset.curve_by_mnemonic(normalized_parameter) is None:
                raise ValueError("Кривая параметрического обозначения отсутствует")
        return (
            normalized_anchor,
            normalized_top,
            normalized_bottom,
            normalized_width,
            normalized_height,
            normalized_label,
            normalized_parameter,
            normalized_time,
        )

    def _require_template(self, template_id: str) -> MasterlogTemplate:
        try:
            return self.session.project.masterlog_templates[template_id]
        except KeyError as exc:
            raise KeyError(f"Форма masterlog не найдена: {template_id}") from exc

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well

    def _require_item(self, object_id: str, template_id: str) -> CanvasObject:
        for item in self._require_well().canvas_objects:
            if (
                item.object_id == object_id
                and item.object_type == MASTERLOG_SYMBOL_TYPE
                and item.properties.get("template_id") == template_id
            ):
                return item
        raise KeyError(f"Обозначение masterlog не найдено: {object_id}")

    @staticmethod
    def _to_symbol(item: CanvasObject) -> PlacedMasterlogSymbol:
        return PlacedMasterlogSymbol(
            item.object_id,
            item.anchor_type
            if item.anchor_type in {"depth", "interval", "parameter", "time"}
            else "depth",
            float(item.top_depth if item.top_depth is not None else item.y),
            float(
                item.bottom_depth
                if item.bottom_depth is not None
                else item.top_depth
                if item.top_depth is not None
                else item.y
            ),
            str(item.track_id or ""),
            str(item.properties.get("asset_ref", "")),
            float(item.width),
            float(item.height),
            str(item.properties.get("label", "")),
            item.parameter_mnemonic,
            item.time_value,
        )
