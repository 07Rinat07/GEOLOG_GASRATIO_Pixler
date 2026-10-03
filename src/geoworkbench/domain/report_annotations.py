from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from math import isfinite
from typing import Any
from uuid import uuid4

from geoworkbench.domain.annotation_style import ANNOTATION_STYLE_KEYS, AnnotationStyle
from geoworkbench.domain.localized_content import validate_localized_texts


REPORT_ANNOTATION_SCHEMA_VERSION = 1
REPORT_ANNOTATION_TEXT_MAXIMUM = 10_000
REPORT_ANNOTATION_ID_MAXIMUM = 128
REPORT_ANNOTATION_SCOPE_MAXIMUM = 512
REPORT_TRACK_KEY_MAXIMUM = 200

_FIXED_REPORT_TRACK_KEYS = frozenset(
    {
        "geology:cuttings",
        "geology:lba",
        "depth:left",
        "depth:right",
    }
)


class ReportAnnotationKind(StrEnum):
    TEXT = "text"
    CALLOUT = "callout"
    ARROW = "arrow"
    INTERVAL_HIGHLIGHT = "interval_highlight"
    REMARK = "remark"


class ReportAnnotationAnchor(StrEnum):
    DEPTH = "depth"
    INTERVAL = "interval"
    TRACK = "track"


@dataclass(frozen=True, slots=True)
class ReportAnnotationRecord:
    """Persisted renderer-neutral annotation owned by one report composition."""

    annotation_id: str
    scope_id: str
    kind: ReportAnnotationKind
    anchor: ReportAnnotationAnchor
    text: str = ""
    track_key: str | None = None
    depth: float | None = None
    top_depth: float | None = None
    bottom_depth: float | None = None
    x_fraction: float = 0.5
    offset_x: float = 18.0
    offset_y: float = -36.0
    width: float = 220.0
    height: float = 76.0
    style: AnnotationStyle = field(default_factory=AnnotationStyle)
    visible: bool = True
    locked: bool = False
    print_enabled: bool = True
    text_i18n: dict[str, str] = field(default_factory=dict)


_REPORT_ANNOTATION_KEYS = frozenset(
    {
        "schema_version",
        "annotation_id",
        "scope_id",
        "kind",
        "anchor",
        "text",
        "track_key",
        "depth",
        "top_depth",
        "bottom_depth",
        "x_fraction",
        "offset_x",
        "offset_y",
        "width",
        "height",
        "style",
        "visible",
        "locked",
        "print_enabled",
        "text_i18n",
    }
)


def report_annotation_scope_id(
    well_id: str,
    dataset_id: str,
    composition_id: str,
) -> str:
    """Return the explicit ownership scope required for report annotations."""

    well = _required_identifier(well_id, "Well ID")
    dataset = _required_identifier(dataset_id, "Dataset ID")
    composition = _required_identifier(composition_id, "Report composition ID")
    scope = f"report:{well}:{dataset}:{composition}"
    if len(scope) > REPORT_ANNOTATION_SCOPE_MAXIMUM:
        raise ValueError("Область report annotation превышает допустимый размер")
    return scope


def normalize_report_track_key(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Logical report-track key должен быть строкой")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > REPORT_TRACK_KEY_MAXIMUM:
        raise ValueError("Logical report-track key превышает допустимый размер")
    if any(character.isspace() or ord(character) < 32 for character in normalized):
        raise ValueError(
            "Logical report-track key не должен содержать пробелы или control characters"
        )
    if normalized in _FIXED_REPORT_TRACK_KEYS:
        return normalized
    if normalized.startswith("curve:") and len(normalized) > len("curve:"):
        return normalized
    raise ValueError(f"Неподдерживаемый logical report-track key: {normalized!r}")


def new_report_annotation_id() -> str:
    return f"rann-{uuid4().hex}"


def validate_report_annotation(record: ReportAnnotationRecord) -> ReportAnnotationRecord:
    annotation_id = _bounded_required_text(
        record.annotation_id,
        "ID report annotation",
        REPORT_ANNOTATION_ID_MAXIMUM,
    )
    scope_id = _bounded_required_text(
        record.scope_id,
        "Область report annotation",
        REPORT_ANNOTATION_SCOPE_MAXIMUM,
    )
    try:
        kind = ReportAnnotationKind(record.kind)
        anchor = ReportAnnotationAnchor(record.anchor)
    except ValueError as exc:
        raise ValueError("Некорректный тип или anchor report annotation") from exc

    text = _bounded_text(record.text, "Текст report annotation", REPORT_ANNOTATION_TEXT_MAXIMUM)
    text_i18n = validate_localized_texts(
        record.text_i18n,
        maximum=REPORT_ANNOTATION_TEXT_MAXIMUM,
    )
    if not isinstance(record.style, AnnotationStyle):
        raise ValueError("Некорректный стиль report annotation")
    visible = _strict_bool(record.visible, "visible")
    locked = _strict_bool(record.locked, "locked")
    print_enabled = _strict_bool(record.print_enabled, "print_enabled")
    track_key = normalize_report_track_key(record.track_key)
    depth = _optional_finite(record.depth, "Глубина report annotation")
    top_depth = _optional_finite(record.top_depth, "Верх report annotation")
    bottom_depth = _optional_finite(record.bottom_depth, "Низ report annotation")

    if anchor is ReportAnnotationAnchor.DEPTH:
        if depth is None:
            raise ValueError("Depth-anchored report annotation требует глубину")
        if top_depth is not None or bottom_depth is not None:
            raise ValueError("Depth-anchored report annotation не может содержать interval")
    elif anchor is ReportAnnotationAnchor.INTERVAL:
        if depth is not None or top_depth is None or bottom_depth is None:
            raise ValueError("Interval-anchored report annotation требует верх и низ")
        if top_depth > bottom_depth:
            raise ValueError("Верх report annotation не может быть глубже низа")
    else:
        if track_key is None:
            raise ValueError("Track-anchored report annotation требует logical track key")
        if depth is not None or top_depth is not None or bottom_depth is not None:
            raise ValueError("Track-anchored report annotation не может содержать depth interval")

    if (
        kind is ReportAnnotationKind.INTERVAL_HIGHLIGHT
        and anchor is not ReportAnnotationAnchor.INTERVAL
    ):
        raise ValueError("Interval highlight должен быть привязан к интервалу")

    x_fraction = _bounded_number(record.x_fraction, "X report annotation", 0.0, 1.0)
    offset_x = _bounded_number(
        record.offset_x, "Offset X report annotation", -10_000.0, 10_000.0
    )
    offset_y = _bounded_number(
        record.offset_y, "Offset Y report annotation", -10_000.0, 10_000.0
    )
    width = _bounded_number(record.width, "Ширина report annotation", 1.0, 4_000.0)
    height = _bounded_number(record.height, "Высота report annotation", 1.0, 4_000.0)

    return replace(
        record,
        annotation_id=annotation_id,
        scope_id=scope_id,
        kind=kind,
        anchor=anchor,
        text=text,
        track_key=track_key,
        depth=depth,
        top_depth=top_depth,
        bottom_depth=bottom_depth,
        x_fraction=x_fraction,
        offset_x=offset_x,
        offset_y=offset_y,
        width=width,
        height=height,
        visible=visible,
        locked=locked,
        print_enabled=print_enabled,
        text_i18n=text_i18n,
    )


def report_annotation_to_dict(record: ReportAnnotationRecord) -> dict[str, Any]:
    item = validate_report_annotation(record)
    return {
        "schema_version": REPORT_ANNOTATION_SCHEMA_VERSION,
        "annotation_id": item.annotation_id,
        "scope_id": item.scope_id,
        "kind": item.kind.value,
        "anchor": item.anchor.value,
        "text": item.text,
        "track_key": item.track_key,
        "depth": item.depth,
        "top_depth": item.top_depth,
        "bottom_depth": item.bottom_depth,
        "x_fraction": item.x_fraction,
        "offset_x": item.offset_x,
        "offset_y": item.offset_y,
        "width": item.width,
        "height": item.height,
        "style": item.style.to_dict(),
        "visible": item.visible,
        "locked": item.locked,
        "print_enabled": item.print_enabled,
        "text_i18n": dict(item.text_i18n),
    }


def report_annotation_from_mapping(value: Mapping[str, Any]) -> ReportAnnotationRecord:
    if not isinstance(value, Mapping) or set(value) != _REPORT_ANNOTATION_KEYS:
        raise ValueError("Некорректная persisted report annotation")
    version = value.get("schema_version")
    if version != REPORT_ANNOTATION_SCHEMA_VERSION:
        raise ValueError("Неподдерживаемая версия report annotation")

    raw_style = value.get("style")
    if not isinstance(raw_style, Mapping) or set(raw_style) - ANNOTATION_STYLE_KEYS:
        raise ValueError("Некорректный стиль report annotation")

    raw_i18n = value.get("text_i18n")
    if not isinstance(raw_i18n, Mapping):
        raise ValueError("Некорректный многоязычный текст report annotation")

    try:
        record = ReportAnnotationRecord(
            annotation_id=value["annotation_id"],
            scope_id=value["scope_id"],
            kind=ReportAnnotationKind(value["kind"]),
            anchor=ReportAnnotationAnchor(value["anchor"]),
            text=value["text"],
            track_key=value["track_key"],
            depth=value["depth"],
            top_depth=value["top_depth"],
            bottom_depth=value["bottom_depth"],
            x_fraction=value["x_fraction"],
            offset_x=value["offset_x"],
            offset_y=value["offset_y"],
            width=value["width"],
            height=value["height"],
            style=AnnotationStyle.from_mapping(raw_style),
            visible=_strict_bool(value["visible"], "visible"),
            locked=_strict_bool(value["locked"], "locked"),
            print_enabled=_strict_bool(value["print_enabled"], "print_enabled"),
            text_i18n=dict(raw_i18n),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Некорректная persisted report annotation") from exc
    return validate_report_annotation(record)


def _required_identifier(value: str, label: str) -> str:
    return _bounded_required_text(value, label, 200)


def _bounded_required_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} должен быть строкой")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} не может быть пустым")
    if len(normalized) > maximum:
        raise ValueError(f"{label} превышает допустимый размер")
    return normalized


def _bounded_text(value: object, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} должен быть строкой")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValueError(f"{label} превышает допустимый размер")
    return normalized


def _optional_finite(value: object, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} должна быть конечным числом")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{label} должна быть конечным числом")
    return normalized


def _bounded_number(value: object, label: str, minimum: float, maximum: float) -> float:
    normalized = _optional_finite(value, label)
    if normalized is None or not minimum <= normalized <= maximum:
        raise ValueError(f"{label} выходит за допустимый диапазон")
    return normalized


def _strict_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} report annotation должен быть boolean")
    return value


__all__ = [
    "REPORT_ANNOTATION_SCHEMA_VERSION",
    "ReportAnnotationAnchor",
    "ReportAnnotationKind",
    "ReportAnnotationRecord",
    "new_report_annotation_id",
    "normalize_report_track_key",
    "report_annotation_from_mapping",
    "report_annotation_scope_id",
    "report_annotation_to_dict",
    "validate_report_annotation",
]
