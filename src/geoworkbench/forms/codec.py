from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any

from geoworkbench.forms.models import (
    FormAxisKind,
    FormColumn,
    FormDocument,
    FormTemplateOrigin,
    FormTrack,
    ParameterBinding,
)
from geoworkbench.tablet.models import CurveLineStyle, CurveStyle, TrackKind, XScale


FORM_SCHEMA_VERSION = 1


class FormFormatError(ValueError):
    """Raised when a form template cannot be decoded safely."""


def form_to_dict(form: FormDocument) -> dict[str, Any]:
    form.validate()
    return {
        "schema_version": FORM_SCHEMA_VERSION,
        "form_id": form.form_id,
        "name": form.name,
        "description": form.description,
        "axis_kind": form.axis_kind.value,
        "origin": form.origin.value,
        "read_only": form.read_only,
        "style_id": form.style_id,
        "print_header_template_id": form.print_header_template_id,
        "columns": [
            {
                "column_id": column.column_id,
                "title": column.title,
                "group_title": column.group_title,
                "width": column.width,
                "visible": column.visible,
                "locked": column.locked,
                "tracks": [
                    {
                        "track_id": track.track_id,
                        "title": track.title,
                        "kind": track.kind.value,
                        "visible": track.visible,
                        "locked": track.locked,
                        "grid_x": track.grid_x,
                        "grid_y": track.grid_y,
                        "grid_alpha": track.grid_alpha,
                        "x_axis_label": track.x_axis_label,
                        "bindings": [_binding_to_dict(binding) for binding in track.bindings],
                    }
                    for track in column.tracks
                ],
            }
            for column in form.columns
        ],
    }


def form_from_dict(data: object) -> FormDocument:
    if not isinstance(data, dict):
        raise FormFormatError("Форма должна быть JSON-объектом")
    migrated = _migrate_form(data)
    try:
        columns = [_column_from_dict(item) for item in _list(migrated, "columns")]
        return FormDocument(
            form_id=_string(migrated, "form_id"),
            name=_string(migrated, "name"),
            description=_string(migrated, "description", allow_empty=True, default=""),
            axis_kind=FormAxisKind(_string(migrated, "axis_kind")),
            origin=FormTemplateOrigin(
                _string(migrated, "origin", default=FormTemplateOrigin.USER.value)
            ),
            read_only=_boolean(migrated, "read_only", default=False),
            style_id=_string(migrated, "style_id", default="default-screen"),
            print_header_template_id=_optional_string(migrated, "print_header_template_id"),
            columns=columns,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise FormFormatError("Некорректная структура формы") from exc


def _binding_to_dict(binding: ParameterBinding) -> dict[str, Any]:
    return {
        "binding_id": binding.binding_id,
        "canonical_parameter_id": binding.canonical_parameter_id,
        "display_name": binding.display_name,
        "source_mnemonic": binding.source_mnemonic,
        "unit": binding.unit,
        "visible": binding.visible,
        "style": {
            "color": binding.style.color,
            "width": binding.style.width,
            "line_style": binding.style.line_style.value,
        },
        "x_scale": binding.x_scale.value,
        "x_min": binding.x_min,
        "x_max": binding.x_max,
    }


def _binding_from_dict(data: object) -> ParameterBinding:
    if not isinstance(data, dict):
        raise TypeError("Привязка должна быть JSON-объектом")
    style = data.get("style", {})
    if not isinstance(style, dict):
        raise TypeError("style должен быть JSON-объектом")
    x_scale = XScale(_string(data, "x_scale", default=XScale.LINEAR.value))
    x_min, x_max = _normalized_range(
        x_scale,
        _optional_number(data, "x_min"),
        _optional_number(data, "x_max"),
    )
    return ParameterBinding(
        binding_id=_string(data, "binding_id"),
        canonical_parameter_id=_string(data, "canonical_parameter_id"),
        display_name=_string(data, "display_name"),
        source_mnemonic=_optional_string(data, "source_mnemonic"),
        unit=_string(data, "unit", allow_empty=True, default=""),
        visible=_boolean(data, "visible", default=True),
        style=CurveStyle(
            color=str(style.get("color", "#2563eb")),
            width=float(style.get("width", 1.5)),
            line_style=CurveLineStyle(str(style.get("line_style", "solid"))),
        ),
        x_scale=x_scale,
        x_min=x_min,
        x_max=x_max,
    )


def _normalized_range(
    scale: XScale, minimum: float | None, maximum: float | None
) -> tuple[float | None, float | None]:
    """Repair legacy/manual curve ranges without blocking the form manager.

    Old user forms and sensor catalogs can contain one missing bound, equal
    placeholders (``0 .. 0``), reversed limits, or non-finite values.  These
    records are recoverable: reversed finite limits are ordered, while ranges
    that cannot be plotted safely fall back to autoscale.
    """

    if minimum is None or maximum is None:
        return None, None
    if not isfinite(minimum) or not isfinite(maximum):
        return None, None
    low, high = sorted((float(minimum), float(maximum)))
    if low == high:
        return None, None
    if scale is XScale.LOGARITHMIC and low <= 0:
        return None, None
    return low, high


def _track_from_dict(data: object) -> FormTrack:
    if not isinstance(data, dict):
        raise TypeError("Дорожка должна быть JSON-объектом")
    return FormTrack(
        track_id=_string(data, "track_id"),
        title=_string(data, "title"),
        kind=TrackKind(_string(data, "kind")),
        visible=_boolean(data, "visible", default=True),
        locked=_boolean(data, "locked", default=False),
        grid_x=_boolean(data, "grid_x", default=True),
        grid_y=_boolean(data, "grid_y", default=True),
        grid_alpha=float(_number(data, "grid_alpha", default=0.2)),
        x_axis_label=_string(data, "x_axis_label", allow_empty=True, default=""),
        bindings=[_binding_from_dict(item) for item in _list(data, "bindings", default=[])],
    )


def _column_from_dict(data: object) -> FormColumn:
    if not isinstance(data, dict):
        raise TypeError("Колонка должна быть JSON-объектом")
    return FormColumn(
        column_id=_string(data, "column_id"),
        title=_string(data, "title"),
        group_title=_string(data, "group_title", allow_empty=True, default=""),
        width=int(_number(data, "width", default=260)),
        visible=_boolean(data, "visible", default=True),
        locked=_boolean(data, "locked", default=False),
        tracks=[_track_from_dict(item) for item in _list(data, "tracks", default=[])],
    )


def _migrate_form(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("schema_version", 0)
    if version == FORM_SCHEMA_VERSION:
        return data
    if version != 0:
        raise FormFormatError("Неподдерживаемая версия схемы формы")
    migrated = deepcopy(data)
    migrated["schema_version"] = 1
    migrated.setdefault("description", "")
    migrated.setdefault("origin", FormTemplateOrigin.USER.value)
    migrated.setdefault("read_only", False)
    migrated.setdefault("style_id", "default-screen")
    migrated.setdefault("print_header_template_id", None)
    migrated.setdefault("columns", [])
    return migrated


def _string(
    data: dict[str, Any], key: str, *, allow_empty: bool = False, default: str | None = None
) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise TypeError(f"{key} должен быть строкой")
    return value


def _optional_string(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{key} должен быть строкой или null")
    return value


def _boolean(data: dict[str, Any], key: str, *, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise TypeError(f"{key} должен быть логическим")
    return value


def _number(data: dict[str, Any], key: str, *, default: float | int) -> float | int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} должен быть числом")
    return value


def _optional_number(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} должен быть числом или null")
    return float(value)


def _list(data: dict[str, Any], key: str, *, default: list[Any] | None = None) -> list[Any]:
    value = data.get(key, default)
    if not isinstance(value, list):
        raise TypeError(f"{key} должен быть списком")
    return value
