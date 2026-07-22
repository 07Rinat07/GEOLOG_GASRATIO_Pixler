from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from enum import StrEnum
from math import isfinite
from typing import Any, Mapping

from geoworkbench.domain.models import CanvasObject


ANNOTATION_OBJECT_TYPE = "annotation"
LEGACY_DEPTH_ANNOTATION_TYPE = "depth_annotation"
ANNOTATION_SCHEMA_VERSION = 2


class AnnotationKind(StrEnum):
    CALLOUT = "callout"
    COMMENT = "comment"
    VALUE = "value"
    IMAGE = "image"
    SYMBOL = "symbol"


class AnnotationAnchor(StrEnum):
    TRACK = "track"
    DEPTH = "depth"
    TIME = "time"
    CURVE = "curve"


@dataclass(frozen=True, slots=True)
class AnnotationStyle:
    font_family: str = "Arial"
    font_size: float = 10.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    text_color: str = "#0f172a"
    fill_color: str = "#ffffff"
    fill_opacity: float = 0.94
    border_color: str = "#2563eb"
    border_width: float = 1.2
    border_style: str = "solid"
    corner_radius: float = 6.0
    padding: float = 7.0
    alignment: str = "left"
    vertical_alignment: str = "top"
    leader_color: str = "#2563eb"
    leader_width: float = 1.2
    leader_style: str = "solid"
    arrow_style: str = "triangle"
    shadow: bool = True
    shadow_blur: float = 5.0
    shadow_offset_x: float = 2.0
    shadow_offset_y: float = 2.0
    rotation: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "font_family": self.font_family,
            "font_size": self.font_size,
            "bold": self.bold,
            "italic": self.italic,
            "underline": self.underline,
            "text_color": self.text_color,
            "fill_color": self.fill_color,
            "fill_opacity": self.fill_opacity,
            "border_color": self.border_color,
            "border_width": self.border_width,
            "border_style": self.border_style,
            "corner_radius": self.corner_radius,
            "padding": self.padding,
            "alignment": self.alignment,
            "vertical_alignment": self.vertical_alignment,
            "leader_color": self.leader_color,
            "leader_width": self.leader_width,
            "leader_style": self.leader_style,
            "arrow_style": self.arrow_style,
            "shadow": self.shadow,
            "shadow_blur": self.shadow_blur,
            "shadow_offset_x": self.shadow_offset_x,
            "shadow_offset_y": self.shadow_offset_y,
            "rotation": self.rotation,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> AnnotationStyle:
        raw = dict(value or {})
        return cls(
            font_family=_string(raw.get("font_family"), "Arial", maximum=120),
            font_size=_number(raw.get("font_size"), 10.0, 4.0, 96.0),
            bold=bool(raw.get("bold", False)),
            italic=bool(raw.get("italic", False)),
            underline=bool(raw.get("underline", False)),
            text_color=_color(raw.get("text_color"), "#0f172a"),
            fill_color=_color(raw.get("fill_color"), "#ffffff"),
            fill_opacity=_number(raw.get("fill_opacity"), 0.94, 0.0, 1.0),
            border_color=_color(raw.get("border_color"), "#2563eb"),
            border_width=_number(raw.get("border_width"), 1.2, 0.0, 20.0),
            border_style=_choice(raw.get("border_style"), "solid", {"solid", "dash", "dot"}),
            corner_radius=_number(raw.get("corner_radius"), 6.0, 0.0, 64.0),
            padding=_number(raw.get("padding"), 7.0, 0.0, 64.0),
            alignment=_choice(raw.get("alignment"), "left", {"left", "center", "right"}),
            vertical_alignment=_choice(
                raw.get("vertical_alignment"), "top", {"top", "center", "bottom"}
            ),
            leader_color=_color(raw.get("leader_color"), "#2563eb"),
            leader_width=_number(raw.get("leader_width"), 1.2, 0.0, 20.0),
            leader_style=_choice(raw.get("leader_style"), "solid", {"solid", "dash", "dot"}),
            arrow_style=_choice(
                raw.get("arrow_style"), "triangle", {"none", "triangle", "open", "circle"}
            ),
            shadow=bool(raw.get("shadow", True)),
            shadow_blur=_number(raw.get("shadow_blur"), 5.0, 0.0, 32.0),
            shadow_offset_x=_number(raw.get("shadow_offset_x"), 2.0, -64.0, 64.0),
            shadow_offset_y=_number(raw.get("shadow_offset_y"), 2.0, -64.0, 64.0),
            rotation=_number(raw.get("rotation"), 0.0, -180.0, 180.0),
        )


@dataclass(frozen=True, slots=True)
class AnnotationRecord:
    annotation_id: str
    kind: AnnotationKind
    anchor: AnnotationAnchor
    text: str
    track_id: str | None
    depth: float | None
    axis_value: float | None
    axis_id: str | None
    parameter_mnemonic: str | None
    parameter_value: float | None
    unit: str
    x_fraction: float
    offset_x: float
    offset_y: float
    width: float
    height: float
    style: AnnotationStyle = field(default_factory=AnnotationStyle)
    asset_ref: str | None = None
    visible: bool = True
    locked: bool = False
    print_enabled: bool = True
    scope_id: str | None = None


STYLE_PRESETS: dict[str, AnnotationStyle] = {
    "professional": AnnotationStyle(),
    "information": AnnotationStyle(
        fill_color="#eff6ff",
        border_color="#2563eb",
        leader_color="#2563eb",
        text_color="#1e3a8a",
    ),
    "warning": AnnotationStyle(
        fill_color="#fff7ed",
        border_color="#ea580c",
        leader_color="#ea580c",
        text_color="#7c2d12",
        bold=True,
    ),
    "critical": AnnotationStyle(
        fill_color="#fef2f2",
        border_color="#dc2626",
        leader_color="#dc2626",
        text_color="#7f1d1d",
        bold=True,
    ),
    "neutral": AnnotationStyle(
        fill_color="#f8fafc",
        border_color="#64748b",
        leader_color="#64748b",
        text_color="#0f172a",
        shadow=False,
    ),
}


def is_annotation_object(item: CanvasObject) -> bool:
    return item.object_type in {ANNOTATION_OBJECT_TYPE, LEGACY_DEPTH_ANNOTATION_TYPE}


def annotation_from_canvas(item: CanvasObject) -> AnnotationRecord:
    if item.object_type == LEGACY_DEPTH_ANNOTATION_TYPE:
        depth = item.top_depth if item.top_depth is not None else item.y
        return AnnotationRecord(
            annotation_id=item.object_id,
            kind=AnnotationKind.CALLOUT,
            anchor=AnnotationAnchor.DEPTH,
            text=str(item.properties.get("text", "")),
            track_id=item.track_id,
            depth=float(depth) if _finite(depth) else None,
            axis_value=None,
            axis_id=None,
            parameter_mnemonic=item.parameter_mnemonic,
            parameter_value=None,
            unit="",
            x_fraction=_number(item.x, 0.04, 0.0, 1.0),
            offset_x=_number(item.properties.get("offset_x_px"), 14.0, -10000.0, 10000.0),
            offset_y=_number(item.properties.get("offset_y_px"), -22.0, -10000.0, 10000.0),
            width=_number(item.width, 210.0, 40.0, 4000.0),
            height=_number(item.height, 64.0, 24.0, 4000.0),
            style=AnnotationStyle.from_mapping(item.properties.get("style")),
            visible=bool(item.properties.get("visible", True)),
            locked=bool(item.properties.get("locked", False)),
            print_enabled=bool(item.properties.get("print_enabled", True)),
            scope_id=_optional_string(item.properties.get("scope_id"), maximum=300),
        )
    raw_kind = item.properties.get("kind", AnnotationKind.CALLOUT.value)
    raw_anchor = item.anchor_type or AnnotationAnchor.TRACK.value
    try:
        kind = AnnotationKind(str(raw_kind))
    except ValueError:
        kind = AnnotationKind.CALLOUT
    try:
        anchor = AnnotationAnchor(str(raw_anchor))
    except ValueError:
        anchor = AnnotationAnchor.TRACK
    record_depth = _finite_number(
        item.top_depth if item.top_depth is not None else item.properties.get("depth")
    )
    axis_value = _finite_number(item.properties.get("axis_value"))
    parameter_value = _finite_number(item.properties.get("parameter_value"))
    return AnnotationRecord(
        annotation_id=item.object_id,
        kind=kind,
        anchor=anchor,
        text=str(item.properties.get("text", "")),
        track_id=item.track_id,
        depth=record_depth,
        axis_value=axis_value,
        axis_id=_optional_string(item.properties.get("axis_id"), maximum=200),
        parameter_mnemonic=item.parameter_mnemonic,
        parameter_value=parameter_value,
        unit=_string(item.properties.get("unit"), "", maximum=80),
        x_fraction=_number(item.x, 0.5, 0.0, 1.0),
        offset_x=_number(item.properties.get("offset_x_px"), 18.0, -10000.0, 10000.0),
        offset_y=_number(item.properties.get("offset_y_px"), -36.0, -10000.0, 10000.0),
        width=_number(item.width, 220.0, 40.0, 4000.0),
        height=_number(item.height, 76.0, 24.0, 4000.0),
        style=AnnotationStyle.from_mapping(item.properties.get("style")),
        asset_ref=_optional_string(item.properties.get("asset_ref"), maximum=200),
        visible=bool(item.properties.get("visible", True)),
        locked=bool(item.properties.get("locked", False)),
        print_enabled=bool(item.properties.get("print_enabled", True)),
        scope_id=_optional_string(item.properties.get("scope_id"), maximum=300),
    )


def annotation_properties(
    *,
    kind: AnnotationKind,
    text: str,
    axis_value: float | None,
    axis_id: str | None,
    parameter_value: float | None,
    unit: str,
    offset_x: float,
    offset_y: float,
    style: AnnotationStyle,
    asset_ref: str | None,
    visible: bool,
    locked: bool,
    print_enabled: bool,
    scope_id: str | None = None,
) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "schema_version": ANNOTATION_SCHEMA_VERSION,
        "kind": kind.value,
        "text": text,
        "offset_x_px": float(offset_x),
        "offset_y_px": float(offset_y),
        "style": style.to_dict(),
        "visible": bool(visible),
        "locked": bool(locked),
        "print_enabled": bool(print_enabled),
        "unit": unit,
    }
    if scope_id:
        properties["scope_id"] = scope_id
    if axis_value is not None:
        properties["axis_value"] = float(axis_value)
    if axis_id:
        properties["axis_id"] = axis_id
    if parameter_value is not None:
        properties["parameter_value"] = float(parameter_value)
    if asset_ref:
        properties["asset_ref"] = asset_ref
    return properties


def annotation_scope_id(dataset_id: str | None, layout: object | None) -> str | None:
    """Return a stable view scope for annotations in one dataset/tablet form.

    The scope uses the current dataset plus the ordered track identifiers and
    vertical index. Applying another form therefore does not leak comments into
    that form, while reopening the same saved form/layout restores them.
    """

    if not dataset_id:
        return None
    explicit = getattr(layout, "annotation_scope_id", None) if layout is not None else None
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()[:300]
    raw_tracks = getattr(layout, "tracks", ()) if layout is not None else ()
    track_ids = [
        str(getattr(track, "track_id", "")).strip()
        for track in raw_tracks
        if str(getattr(track, "track_id", "")).strip()
    ]
    payload = "\x1f".join(track_ids or ["empty-layout"])
    digest = sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"dataset:{dataset_id}:tablet:{digest}"


def annotation_scope_id_for_session(session: object) -> str | None:
    return annotation_scope_id(
        getattr(session, "current_dataset_id", None),
        getattr(session, "current_tablet_layout", None),
    )


def annotation_matches_scope(record: AnnotationRecord, scope_id: str | None) -> bool:
    if record.scope_id is None:
        return scope_id is None
    return record.scope_id == scope_id


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(float(value))
    )


def _finite_number(value: object) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    normalized = float(value)
    return normalized if isfinite(normalized) else None


def _number(value: object, default: float, minimum: float, maximum: float) -> float:
    normalized = _finite_number(value)
    if normalized is None:
        return default
    return max(minimum, min(maximum, normalized))


def _string(value: object, default: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip()
    return normalized[:maximum] if normalized else default


def _optional_string(value: object, *, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized[:maximum] if normalized else None


def _choice(value: object, default: str, choices: set[str]) -> str:
    normalized = str(value) if value is not None else default
    return normalized if normalized in choices else default


def _color(value: object, default: str) -> str:
    if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        try:
            int(value[1:], 16)
        except ValueError:
            return default
        return value.lower()
    return default
