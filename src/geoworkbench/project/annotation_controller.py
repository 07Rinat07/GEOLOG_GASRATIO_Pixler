from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

import numpy as np

from geoworkbench.domain.models import CanvasObject, Well, new_id
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.canvas_history import CanvasObjectHistory


DEPTH_ANNOTATION_TYPE = "depth_annotation"


@dataclass(frozen=True, slots=True)
class DepthAnnotation:
    annotation_id: str
    depth: float
    text: str


@dataclass(slots=True)
class DepthAnnotationController:
    session: ProjectSession
    history: CanvasObjectHistory = field(default_factory=CanvasObjectHistory)

    def available(self) -> tuple[DepthAnnotation, ...]:
        annotations = [
            self._to_annotation(item)
            for item in self._require_well().canvas_objects
            if item.object_type == DEPTH_ANNOTATION_TYPE
        ]
        return tuple(sorted(annotations, key=lambda item: (item.depth, item.annotation_id)))

    def add(self, depth: float, text: str) -> DepthAnnotation:
        normalized_depth, normalized_text = self._validate(depth, text)
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        item = CanvasObject(
            object_id=new_id(),
            object_type=DEPTH_ANNOTATION_TYPE,
            anchor_type="depth",
            x=0.0,
            y=normalized_depth,
            width=1.0,
            height=0.0,
            top_depth=normalized_depth,
            bottom_depth=normalized_depth,
            properties={"text": normalized_text},
        )
        well.canvas_objects.append(item)
        self.history.record(well, before, description="Добавление глубинной заметки")
        self.session.dirty = True
        return self._to_annotation(item)

    def update(self, annotation_id: str, *, depth: float, text: str) -> DepthAnnotation:
        normalized_depth, normalized_text = self._validate(depth, text)
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        item = self._require_item(annotation_id)
        item.y = normalized_depth
        item.top_depth = normalized_depth
        item.bottom_depth = normalized_depth
        item.properties["text"] = normalized_text
        self.history.record(well, before, description="Изменение глубинной заметки")
        self.session.dirty = True
        return self._to_annotation(item)

    def remove(self, annotation_id: str) -> DepthAnnotation:
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        item = self._require_item(annotation_id)
        removed = self._to_annotation(item)
        well.canvas_objects.remove(item)
        self.history.record(well, before, description="Удаление глубинной заметки")
        self.session.dirty = True
        return removed

    def undo(self) -> str:
        command = self.history.undo()
        self.session.dirty = True
        return command.description

    def redo(self) -> str:
        command = self.history.redo()
        self.session.dirty = True
        return command.description

    def _validate(self, depth: float, text: str) -> tuple[float, str]:
        normalized_depth = float(depth)
        if not np.isfinite(normalized_depth):
            raise ValueError("Глубина заметки должна быть конечным числом")
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Текст заметки не может быть пустым")
        if len(normalized_text) > 2000:
            raise ValueError("Текст заметки не должен превышать 2000 символов")
        dataset = self.session.current_dataset
        if dataset is not None:
            finite_depth = dataset.depth[np.isfinite(dataset.depth)]
            if finite_depth.size and not (
                float(np.min(finite_depth)) <= normalized_depth <= float(np.max(finite_depth))
            ):
                raise ValueError("Глубина заметки находится вне текущего набора данных")
        return normalized_depth, normalized_text

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well

    def _require_item(self, annotation_id: str) -> CanvasObject:
        for item in self._require_well().canvas_objects:
            if item.object_id == annotation_id and item.object_type == DEPTH_ANNOTATION_TYPE:
                return item
        raise KeyError(f"Заметка не найдена: {annotation_id}")

    @staticmethod
    def _to_annotation(item: CanvasObject) -> DepthAnnotation:
        depth = item.top_depth if item.top_depth is not None else item.y
        return DepthAnnotation(item.object_id, float(depth), str(item.properties.get("text", "")))
