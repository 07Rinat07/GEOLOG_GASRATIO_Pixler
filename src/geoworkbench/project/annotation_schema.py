from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from enum import StrEnum
from math import isfinite
from typing import Any, Mapping

from geoworkbench.domain.annotation_style import AnnotationStyle
from geoworkbench.domain.models import CanvasObject
from geoworkbench.domain.localized_content import validate_localized_texts


ANNOTATION_OBJECT_TYPE = "annotation"
LEGACY_DEPTH_ANNOTATION_TYPE = "depth_annotation"
ANNOTATION_SCHEMA_VERSION = 3
# Catalog symbols may be flattened to a single rendered device pixel.  The
# small positive reference-space floor prevents invalid zero/negative geometry
# while imposing no practical visual width limit.
CATALOG_SYMBOL_MINIMUM_DIMENSION = 0.01


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
        legacy_symbol_id = _optional_string(
            item.properties.get("symbol_id"), maximum=200
        )
        legacy_minimum = CATALOG_SYMBOL_MINIMUM_DIMENSION if legacy_symbol_id else 40.0
        legacy_minimum_height = CATALOG_SYMBOL_MINIMUM_DIMENSION if legacy_symbol_id else 24.0
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
            width=_number(item.width, 210.0, legacy_minimum, 4000.0),
            height=_number(item.height, 64.0, legacy_minimum_height, 4000.0),
            style=AnnotationStyle.from_mapping(item.properties.get("style")),
            visible=bool(item.properties.get("visible", True)),
            locked=bool(item.properties.get("locked", False)),
            print_enabled=bool(item.properties.get("print_enabled", True)),
            scope_id=_optional_string(item.properties.get("scope_id"), maximum=300),
            symbol_id=legacy_symbol_id,
            transparent_background=bool(
                item.properties.get("transparent_background", True)
            ),
            text_i18n=validate_localized_texts(
                item.properties.get("text_i18n"), maximum=10_000
            ),
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
    symbol_id = _optional_string(item.properties.get("symbol_id"), maximum=200)
    symbol_geometry = kind is AnnotationKind.SYMBOL or bool(symbol_id)
    minimum_width = CATALOG_SYMBOL_MINIMUM_DIMENSION if symbol_geometry else 40.0
    minimum_height = CATALOG_SYMBOL_MINIMUM_DIMENSION if symbol_geometry else 24.0
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
        width=_number(item.width, 220.0, minimum_width, 4000.0),
        height=_number(item.height, 76.0, minimum_height, 4000.0),
        style=AnnotationStyle.from_mapping(item.properties.get("style")),
        asset_ref=_optional_string(item.properties.get("asset_ref"), maximum=200),
        visible=bool(item.properties.get("visible", True)),
        locked=bool(item.properties.get("locked", False)),
        print_enabled=bool(item.properties.get("print_enabled", True)),
        scope_id=_optional_string(item.properties.get("scope_id"), maximum=300),
        symbol_id=symbol_id,
        transparent_background=bool(
            item.properties.get("transparent_background", True)
        ),
        text_i18n=validate_localized_texts(
            item.properties.get("text_i18n"), maximum=10_000
        ),
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
    symbol_id: str | None = None,
    transparent_background: bool = True,
    text_i18n: Mapping[str, str] | None = None,
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
    localized = validate_localized_texts(text_i18n, maximum=10_000)
    if localized:
        properties["text_i18n"] = localized
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
    if symbol_id:
        properties["symbol_id"] = symbol_id
        properties["transparent_background"] = bool(transparent_background)
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
