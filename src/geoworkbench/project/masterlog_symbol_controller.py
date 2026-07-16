from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import isfinite

import numpy as np

from geoworkbench.domain.models import CanvasObject, MasterlogTemplate, Well, new_id
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.canvas_history import CanvasObjectHistory


MASTERLOG_SYMBOL_TYPE = "masterlog_symbol"


@dataclass(frozen=True, slots=True)
class PlacedMasterlogSymbol:
    object_id: str
    depth: float
    column_id: str
    asset_ref: str
    width_mm: float
    height_mm: float
    label: str


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
        return tuple(sorted(result, key=lambda item: (item.depth, item.object_id)))

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
    ) -> PlacedMasterlogSymbol:
        values = self._validate(
            template_id, depth, column_id, asset_ref, width_mm, height_mm, label
        )
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        normalized_depth, normalized_width, normalized_height, normalized_label = values
        item = CanvasObject(
            new_id(),
            MASTERLOG_SYMBOL_TYPE,
            "depth",
            0.0,
            normalized_depth,
            normalized_width,
            normalized_height,
            top_depth=normalized_depth,
            bottom_depth=normalized_depth,
            track_id=column_id,
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
    ) -> PlacedMasterlogSymbol:
        values = self._validate(
            template_id, depth, column_id, asset_ref, width_mm, height_mm, label
        )
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        item = self._require_item(object_id, template_id)
        normalized_depth, normalized_width, normalized_height, normalized_label = values
        item.y = normalized_depth
        item.top_depth = normalized_depth
        item.bottom_depth = normalized_depth
        item.track_id = column_id
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
        depth: float,
        column_id: str,
        asset_ref: str,
        width_mm: float,
        height_mm: float,
        label: str,
    ) -> tuple[float, float, float, str]:
        template = self._require_template(template_id)
        if not any(column.column_id == column_id for column in template.columns):
            raise ValueError("Колонка обозначения отсутствует в форме masterlog")
        if asset_ref not in self.session.image_assets:
            raise ValueError("Графический ресурс обозначения отсутствует в проекте")
        numbers = (depth, width_mm, height_mm)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in numbers):
            raise ValueError("Глубина и размеры обозначения должны быть числами")
        normalized_depth = float(depth)
        normalized_width = float(width_mm)
        normalized_height = float(height_mm)
        if not all(isfinite(value) for value in (normalized_depth, normalized_width, normalized_height)):
            raise ValueError("Глубина и размеры обозначения должны быть конечными")
        if not 1.0 <= normalized_width <= 50.0 or not 1.0 <= normalized_height <= 50.0:
            raise ValueError("Размер обозначения должен быть от 1 до 50 мм")
        dataset = self.session.current_dataset
        if dataset is not None:
            finite_depth = dataset.depth[np.isfinite(dataset.depth)]
            if finite_depth.size and not (
                float(np.min(finite_depth)) <= normalized_depth <= float(np.max(finite_depth))
            ):
                raise ValueError("Глубина обозначения находится вне текущего набора данных")
        normalized_label = label.strip()
        if len(normalized_label) > 200:
            raise ValueError("Подпись обозначения не должна превышать 200 символов")
        return normalized_depth, normalized_width, normalized_height, normalized_label

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
            float(item.top_depth if item.top_depth is not None else item.y),
            str(item.track_id or ""),
            str(item.properties.get("asset_ref", "")),
            float(item.width),
            float(item.height),
            str(item.properties.get("label", "")),
        )
