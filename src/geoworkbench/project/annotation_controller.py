from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from geoworkbench.domain.models import CanvasObject, Well, new_id
from geoworkbench.project.annotation_schema import (
    ANNOTATION_OBJECT_TYPE,
    LEGACY_DEPTH_ANNOTATION_TYPE,
    AnnotationAnchor,
    AnnotationKind,
    AnnotationRecord,
    AnnotationStyle,
    annotation_from_canvas,
    annotation_properties,
    is_annotation_object,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.canvas_history import CanvasObjectHistory


if TYPE_CHECKING:
    from geoworkbench.printing.image_assets import ImageAsset
else:
    ImageAsset = Any


DEPTH_ANNOTATION_TYPE = LEGACY_DEPTH_ANNOTATION_TYPE


@dataclass(frozen=True, slots=True)
class DepthAnnotation:
    annotation_id: str
    depth: float
    text: str


@dataclass(slots=True)
class DepthAnnotationController:
    """CRUD service for the well-scoped professional annotation layer.

    The legacy ``add/update/available`` API is intentionally preserved so old
    depth-note dialogs, projects and tests keep working. New UI code should use
    ``available_annotations`` and ``add_annotation``.
    """

    session: ProjectSession
    history: CanvasObjectHistory = field(default_factory=CanvasObjectHistory)

    # ------------------------------------------------------------------
    # Backward-compatible depth-note API
    # ------------------------------------------------------------------
    def available(self) -> tuple[DepthAnnotation, ...]:
        annotations = [
            self._to_depth_annotation(item)
            for item in self._require_well().canvas_objects
            if is_annotation_object(item)
            and annotation_from_canvas(item).depth is not None
        ]
        return tuple(sorted(annotations, key=lambda item: (item.depth, item.annotation_id)))

    def add(self, depth: float, text: str) -> DepthAnnotation:
        normalized_depth, normalized_text = self._validate_depth_text(depth, text)
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        # Preserve the original object type for compatibility with projects and
        # external code that explicitly recognises ``depth_annotation``.
        item = CanvasObject(
            object_id=new_id(),
            object_type=DEPTH_ANNOTATION_TYPE,
            anchor_type=AnnotationAnchor.DEPTH.value,
            x=0.04,
            y=normalized_depth,
            width=210.0,
            height=64.0,
            top_depth=normalized_depth,
            bottom_depth=normalized_depth,
            properties={
                "text": normalized_text,
                "offset_x_px": 14.0,
                "offset_y_px": -22.0,
                "style": AnnotationStyle().to_dict(),
                "visible": True,
                "locked": False,
                "print_enabled": True,
            },
        )
        well.canvas_objects.append(item)
        self.history.record(well, before, description="Добавление глубинной заметки")
        self.session.dirty = True
        return self._to_depth_annotation(item)

    def update(self, annotation_id: str, *, depth: float, text: str) -> DepthAnnotation:
        normalized_depth, normalized_text = self._validate_depth_text(depth, text)
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        item = self._require_item(annotation_id)
        item.y = normalized_depth
        item.top_depth = normalized_depth
        item.bottom_depth = normalized_depth
        item.properties["text"] = normalized_text
        self.history.record(well, before, description="Изменение глубинной заметки")
        self.session.dirty = True
        return self._to_depth_annotation(item)

    # ------------------------------------------------------------------
    # Rich annotation API
    # ------------------------------------------------------------------
    def available_annotations(self) -> tuple[AnnotationRecord, ...]:
        records = [
            annotation_from_canvas(item)
            for item in self._require_well().canvas_objects
            if is_annotation_object(item)
        ]
        return tuple(
            sorted(
                records,
                key=lambda record: (
                    record.depth is None,
                    record.depth if record.depth is not None else float("inf"),
                    record.track_id or "",
                    record.annotation_id,
                ),
            )
        )

    def get(self, annotation_id: str) -> AnnotationRecord:
        return annotation_from_canvas(self._require_item(annotation_id))

    def add_annotation(
        self,
        *,
        kind: AnnotationKind | str = AnnotationKind.CALLOUT,
        anchor: AnnotationAnchor | str = AnnotationAnchor.DEPTH,
        text: str = "",
        track_id: str | None = None,
        depth: float | None = None,
        axis_value: float | None = None,
        axis_id: str | None = None,
        parameter_mnemonic: str | None = None,
        parameter_value: float | None = None,
        unit: str = "",
        x_fraction: float = 0.5,
        offset_x: float = 18.0,
        offset_y: float = -36.0,
        width: float = 220.0,
        height: float = 76.0,
        style: AnnotationStyle | dict[str, object] | None = None,
        asset_ref: str | None = None,
        visible: bool = True,
        locked: bool = False,
        print_enabled: bool = True,
    ) -> AnnotationRecord:
        normalized = self._normalize_annotation(
            kind=kind,
            anchor=anchor,
            text=text,
            track_id=track_id,
            depth=depth,
            axis_value=axis_value,
            axis_id=axis_id,
            parameter_mnemonic=parameter_mnemonic,
            parameter_value=parameter_value,
            unit=unit,
            x_fraction=x_fraction,
            offset_x=offset_x,
            offset_y=offset_y,
            width=width,
            height=height,
            style=style,
            asset_ref=asset_ref,
            visible=visible,
            locked=locked,
            print_enabled=print_enabled,
        )
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        item = self._canvas_from_record(new_id(), normalized)
        well.canvas_objects.append(item)
        self.history.record(well, before, description="Добавление аннотации")
        self.session.dirty = True
        return annotation_from_canvas(item)

    def update_annotation(
        self,
        annotation_id: str,
        **changes: object,
    ) -> AnnotationRecord:
        current = self.get(annotation_id)
        values: dict[str, object] = {
            "kind": current.kind,
            "anchor": current.anchor,
            "text": current.text,
            "track_id": current.track_id,
            "depth": current.depth,
            "axis_value": current.axis_value,
            "axis_id": current.axis_id,
            "parameter_mnemonic": current.parameter_mnemonic,
            "parameter_value": current.parameter_value,
            "unit": current.unit,
            "x_fraction": current.x_fraction,
            "offset_x": current.offset_x,
            "offset_y": current.offset_y,
            "width": current.width,
            "height": current.height,
            "style": current.style,
            "asset_ref": current.asset_ref,
            "visible": current.visible,
            "locked": current.locked,
            "print_enabled": current.print_enabled,
        }
        values.update(changes)
        if (
            "parameter_value" not in changes
            and ("depth" in changes or "parameter_mnemonic" in changes)
        ):
            values["parameter_value"] = None
        if "unit" not in changes and "parameter_mnemonic" in changes:
            values["unit"] = ""
        normalized = self._normalize_annotation(**values)
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        item = self._require_item(annotation_id)
        replacement = self._canvas_from_record(annotation_id, normalized)
        # Keep object identity stable for scene and tree references.
        item.object_type = replacement.object_type
        item.anchor_type = replacement.anchor_type
        item.x = replacement.x
        item.y = replacement.y
        item.width = replacement.width
        item.height = replacement.height
        item.top_depth = replacement.top_depth
        item.bottom_depth = replacement.bottom_depth
        item.time_value = replacement.time_value
        item.parameter_mnemonic = replacement.parameter_mnemonic
        item.track_id = replacement.track_id
        item.properties = replacement.properties
        self.history.record(well, before, description="Изменение аннотации")
        self.session.dirty = True
        return annotation_from_canvas(item)

    def set_geometry(
        self,
        annotation_id: str,
        *,
        offset_x: float,
        offset_y: float,
        width: float,
        height: float,
    ) -> AnnotationRecord:
        return self.update_annotation(
            annotation_id,
            offset_x=offset_x,
            offset_y=offset_y,
            width=width,
            height=height,
        )

    def duplicate(self, annotation_id: str) -> AnnotationRecord:
        current = self.get(annotation_id)
        return self.add_annotation(
            kind=current.kind,
            anchor=current.anchor,
            text=current.text,
            track_id=current.track_id,
            depth=current.depth,
            axis_value=current.axis_value,
            axis_id=current.axis_id,
            parameter_mnemonic=current.parameter_mnemonic,
            parameter_value=current.parameter_value,
            unit=current.unit,
            x_fraction=current.x_fraction,
            offset_x=current.offset_x + 16.0,
            offset_y=current.offset_y + 16.0,
            width=current.width,
            height=current.height,
            style=current.style,
            asset_ref=current.asset_ref,
            visible=current.visible,
            locked=False,
            print_enabled=current.print_enabled,
        )

    def add_curve_value(
        self,
        *,
        track_id: str,
        depth: float,
        axis_value: float,
        axis_id: str | None,
        mnemonic: str,
        value: float,
        unit: str = "",
        x_fraction: float = 0.5,
        display_text: str | None = None,
    ) -> AnnotationRecord:
        suffix = f" {unit.strip()}" if unit.strip() else ""
        annotation_text = (display_text or "").strip() or f"{mnemonic}: {value:g}{suffix}"
        if display_text and not annotation_text.startswith(f"{mnemonic}:"):
            annotation_text = f"{mnemonic}: {annotation_text}"
        return self.add_annotation(
            kind=AnnotationKind.VALUE,
            anchor=AnnotationAnchor.CURVE,
            text=annotation_text,
            track_id=track_id,
            depth=depth,
            axis_value=axis_value,
            axis_id=axis_id,
            parameter_mnemonic=mnemonic,
            parameter_value=value,
            unit=unit,
            x_fraction=x_fraction,
            offset_x=14.0,
            offset_y=-28.0,
            width=175.0,
            height=46.0,
            style=AnnotationStyle(
                font_size=9.0,
                bold=True,
                fill_color="#f8fafc",
                fill_opacity=0.97,
                border_color="#0f766e",
                leader_color="#0f766e",
                text_color="#134e4a",
                corner_radius=5.0,
                padding=6.0,
                shadow=True,
            ),
        )

    def remove(self, annotation_id: str) -> DepthAnnotation | AnnotationRecord:
        well = self._require_well()
        before = deepcopy(well.canvas_objects)
        item = self._require_item(annotation_id)
        legacy = item.object_type == DEPTH_ANNOTATION_TYPE
        removed: DepthAnnotation | AnnotationRecord = (
            self._to_depth_annotation(item) if legacy else annotation_from_canvas(item)
        )
        well.canvas_objects.remove(item)
        self.history.record(
            well,
            before,
            description="Удаление глубинной заметки" if legacy else "Удаление аннотации",
        )
        self.session.dirty = True
        return removed

    def install_image(self, source: str | Path) -> ImageAsset:
        from geoworkbench.printing.image_assets import (
            create_raster_asset,
            create_svg_asset,
            validate_image_asset,
        )

        path = Path(source)
        asset = (
            create_svg_asset(path)
            if path.suffix.casefold() == ".svg"
            else create_raster_asset(path)
        )
        validate_image_asset(asset.asset_id, asset)
        existing = self.session.image_assets.get(asset.asset_id)
        if existing is not None:
            return existing
        self.session.image_assets[asset.asset_id] = asset
        self.session.dirty = True
        return asset

    def undo(self) -> str:
        command = self.history.undo()
        self.session.dirty = True
        return command.description

    def redo(self) -> str:
        command = self.history.redo()
        self.session.dirty = True
        return command.description

    # ------------------------------------------------------------------
    # Validation and conversion
    # ------------------------------------------------------------------
    def _validate_depth_text(self, depth: float, text: str) -> tuple[float, str]:
        normalized_depth = self._validate_depth(depth)
        normalized_text = self._validate_text(text, required=True)
        return normalized_depth, normalized_text

    def _normalize_annotation(self, **values: object) -> AnnotationRecord:
        try:
            kind = (
                values["kind"]
                if isinstance(values["kind"], AnnotationKind)
                else AnnotationKind(str(values["kind"]))
            )
            anchor = (
                values["anchor"]
                if isinstance(values["anchor"], AnnotationAnchor)
                else AnnotationAnchor(str(values["anchor"]))
            )
        except (KeyError, ValueError) as exc:
            raise ValueError("Тип или привязка аннотации не поддерживается") from exc

        text = self._validate_text(
            str(values.get("text", "")),
            required=kind not in {AnnotationKind.IMAGE, AnnotationKind.SYMBOL},
        )
        depth_raw = values.get("depth")
        depth = self._validate_depth(depth_raw) if depth_raw is not None else None
        axis_value = self._optional_finite(values.get("axis_value"), "Координата времени")
        parameter_value = self._optional_finite(values.get("parameter_value"), "Значение параметра")
        if (
            anchor
            in {AnnotationAnchor.DEPTH, AnnotationAnchor.CURVE, AnnotationAnchor.TRACK}
            and depth is None
        ):
            raise ValueError("Для аннотации необходимо указать глубину")
        if anchor is AnnotationAnchor.TIME and axis_value is None and depth is None:
            raise ValueError("Для временной аннотации необходимо указать время или глубину")

        track_id = self._optional_text(values.get("track_id"), 200)
        self._validate_track(track_id)
        parameter = self._optional_text(values.get("parameter_mnemonic"), 200)
        if anchor is AnnotationAnchor.CURVE and not parameter:
            raise ValueError("Для привязки к кривой необходимо выбрать параметр")
        unit = str(values.get("unit", "")).strip()[:80]
        if parameter:
            self._validate_parameter(parameter)
            if (
                anchor is AnnotationAnchor.CURVE
                and depth is not None
                and parameter_value is None
            ):
                sampled = self._parameter_sample(parameter, depth)
                if sampled is not None:
                    parameter_value, sampled_unit = sampled
                    if not unit:
                        unit = sampled_unit

        asset_ref = self._optional_text(values.get("asset_ref"), 200)
        if kind in {AnnotationKind.IMAGE, AnnotationKind.SYMBOL}:
            if not asset_ref:
                raise ValueError("Для изображения или обозначения необходимо выбрать файл")
            if asset_ref not in self.session.image_assets:
                raise ValueError("Графический ресурс аннотации не найден в проекте")

        style_raw = values.get("style")
        style = (
            style_raw
            if isinstance(style_raw, AnnotationStyle)
            else AnnotationStyle.from_mapping(
                style_raw if isinstance(style_raw, dict) else None
            )
        )
        return AnnotationRecord(
            annotation_id="",
            kind=kind,
            anchor=anchor,
            text=text,
            track_id=track_id,
            depth=depth,
            axis_value=axis_value,
            axis_id=self._optional_text(values.get("axis_id"), 200),
            parameter_mnemonic=parameter,
            parameter_value=parameter_value,
            unit=unit,
            x_fraction=self._bounded(values.get("x_fraction"), 0.5, 0.0, 1.0, "Позиция по ширине"),
            offset_x=self._bounded(values.get("offset_x"), 18.0, -10000.0, 10000.0, "Смещение X"),
            offset_y=self._bounded(values.get("offset_y"), -36.0, -10000.0, 10000.0, "Смещение Y"),
            width=self._bounded(values.get("width"), 220.0, 40.0, 4000.0, "Ширина"),
            height=self._bounded(values.get("height"), 76.0, 24.0, 4000.0, "Высота"),
            style=style,
            asset_ref=asset_ref,
            visible=bool(values.get("visible", True)),
            locked=bool(values.get("locked", False)),
            print_enabled=bool(values.get("print_enabled", True)),
        )

    @staticmethod
    def _canvas_from_record(object_id: str, record: AnnotationRecord) -> CanvasObject:
        y = (
            record.axis_value
            if record.anchor is AnnotationAnchor.TIME and record.axis_value is not None
            else (record.depth or 0.0)
        )
        return CanvasObject(
            object_id=object_id,
            object_type=ANNOTATION_OBJECT_TYPE,
            anchor_type=record.anchor.value,
            x=record.x_fraction,
            y=float(y),
            width=record.width,
            height=record.height,
            top_depth=record.depth,
            bottom_depth=record.depth,
            time_value=(
                str(record.axis_value)
                if record.anchor is AnnotationAnchor.TIME
                and record.axis_value is not None
                else None
            ),
            parameter_mnemonic=record.parameter_mnemonic,
            track_id=record.track_id,
            properties=annotation_properties(
                kind=record.kind,
                text=record.text,
                axis_value=record.axis_value,
                axis_id=record.axis_id,
                parameter_value=record.parameter_value,
                unit=record.unit,
                offset_x=record.offset_x,
                offset_y=record.offset_y,
                style=record.style,
                asset_ref=record.asset_ref,
                visible=record.visible,
                locked=record.locked,
                print_enabled=record.print_enabled,
            ),
        )

    def _validate_depth(self, depth: object) -> float:
        try:
            normalized_depth = float(depth)
        except (TypeError, ValueError) as exc:
            raise ValueError("Глубина аннотации должна быть числом") from exc
        if not np.isfinite(normalized_depth):
            raise ValueError("Глубина аннотации должна быть конечным числом")
        dataset = self.session.current_dataset
        if dataset is not None:
            finite_depth = dataset.depth[np.isfinite(dataset.depth)]
            if finite_depth.size and not (
                float(np.min(finite_depth)) <= normalized_depth <= float(np.max(finite_depth))
            ):
                raise ValueError("Глубина аннотации находится вне текущего набора данных")
        return normalized_depth

    @staticmethod
    def _validate_text(text: str, *, required: bool) -> str:
        normalized = text.strip()
        if required and not normalized:
            raise ValueError("Текст аннотации не может быть пустым")
        if len(normalized) > 10_000:
            raise ValueError("Текст аннотации не должен превышать 10000 символов")
        return normalized

    def _validate_track(self, track_id: str | None) -> None:
        if not track_id:
            return
        layout = self.session.current_tablet_layout
        if layout is None:
            return
        if not any(track.track_id == track_id for track in layout.tracks):
            raise ValueError("Выбранная дорожка отсутствует в текущей форме")

    def _validate_parameter(self, mnemonic: str) -> None:
        dataset = self.session.current_dataset
        if dataset is not None and dataset.curve_by_mnemonic(mnemonic) is None:
            raise ValueError(f"Параметр не найден в текущем наборе данных: {mnemonic}")

    def _parameter_sample(self, mnemonic: str, depth: float) -> tuple[float, str] | None:
        dataset = self.session.current_dataset
        if dataset is None:
            return None
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None or curve.values.size != dataset.depth.size:
            return None
        finite = np.flatnonzero(np.isfinite(dataset.depth) & np.isfinite(curve.values))
        if not finite.size:
            return None
        row = int(finite[np.argmin(np.abs(dataset.depth[finite] - float(depth)))])
        return float(curve.values[row]), (curve.metadata.unit or "").strip()

    @staticmethod
    def _optional_finite(value: object, label: str) -> float | None:
        if value is None or value == "":
            return None
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} должно быть числом") from exc
        if not np.isfinite(result):
            raise ValueError(f"{label} должно быть конечным числом")
        return result

    @staticmethod
    def _bounded(
        value: object,
        default: float,
        minimum: float,
        maximum: float,
        label: str,
    ) -> float:
        if value is None:
            return default
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} должно быть числом") from exc
        if not np.isfinite(result) or not minimum <= result <= maximum:
            raise ValueError(f"{label} должно быть от {minimum:g} до {maximum:g}")
        return result

    @staticmethod
    def _optional_text(value: object, maximum: int) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized[:maximum] if normalized else None

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well

    def _require_item(self, annotation_id: str) -> CanvasObject:
        for item in self._require_well().canvas_objects:
            if item.object_id == annotation_id and is_annotation_object(item):
                return item
        raise KeyError(f"Аннотация не найдена: {annotation_id}")

    @staticmethod
    def _to_depth_annotation(item: CanvasObject) -> DepthAnnotation:
        record = annotation_from_canvas(item)
        depth = record.depth if record.depth is not None else item.y
        return DepthAnnotation(item.object_id, float(depth), record.text)


# New code may use the clearer name without breaking existing imports.
AnnotationController = DepthAnnotationController
