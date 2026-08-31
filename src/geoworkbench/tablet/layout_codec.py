from __future__ import annotations

from copy import deepcopy
from typing import Any

from geoworkbench.tablet.models import (
    COMPACT_TRACK_KINDS,
    CurveDisplaySettings,
    CurveLineStyle,
    CurveStyle,
    TabletLayout,
    TrackDefinition,
    TrackKind,
    XScale,
    compact_track_title_orientation,
    compact_track_title_position,
    compact_track_width,
)
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    VerticalRulerScaleSettings,
    VerticalRulerTrackSettings,
)


LAYOUT_FORMAT_VERSION = 24


class TabletLayoutFormatError(ValueError):
    """Raised when persisted tablet layout data is invalid or unsupported."""


def layout_to_dict(layout: TabletLayout) -> dict[str, Any]:
    return {
        "version": LAYOUT_FORMAT_VERSION,
        "visible_depth_top": layout.visible_depth_top,
        "visible_depth_bottom": layout.visible_depth_bottom,
        "cursor_depth": layout.cursor_depth,
        "vertical_index_id": layout.vertical_index_id,
        "annotation_scope_id": layout.annotation_scope_id,
        "localize_factory_labels": layout.localize_factory_labels,
        "vertical_ruler_scale": {
            "major_step": layout.vertical_ruler_scale.major_step,
            "minor_divisions": layout.vertical_ruler_scale.minor_divisions,
        },
        "tracks": [
            {
                "track_id": track.track_id,
                "title": track.title,
                "group_title": track.group_title,
                "title_orientation": track.title_orientation,
                "title_position": track.title_position,
                "show_interval_labels": track.show_interval_labels,
                "lba_label_orientation": track.lba_label_orientation,
                "calcimetry_label_orientation": track.calcimetry_label_orientation,
                "show_description_borders": track.show_description_borders,
                "vertical_ruler": {
                    "mode": track.vertical_ruler.mode.value,
                    "label_every_major": (
                        track.vertical_ruler.label_every_major
                    ),
                    "major_tick_every": (
                        track.vertical_ruler.major_tick_every
                    ),
                    "minor_tick_every": (
                        track.vertical_ruler.minor_tick_every
                    ),
                },
                "kind": track.kind.value,
                "curve_mnemonics": list(track.curve_mnemonics),
                "width": track.width,
                "visible": track.visible,
                "locked": track.locked,
                "x_scale": track.x_scale.value,
                "x_min": track.x_min,
                "x_max": track.x_max,
                "curve_styles": {
                    mnemonic: {
                        "color": style.color,
                        "width": style.width,
                        "line_style": style.line_style.value,
                    }
                    for mnemonic, style in track.curve_styles.items()
                },
                "curve_display": {
                    mnemonic: {
                        "display_name": settings.display_name,
                        "x_scale": settings.x_scale.value,
                        "x_min": settings.x_min,
                        "x_max": settings.x_max,
                        "unit_override": settings.unit_override,
                        "header_text_color": settings.header_text_color,
                        "header_line_color": settings.header_line_color,
                    }
                    for mnemonic, settings in track.curve_display.items()
                },
                "grid_x": track.grid_x,
                "grid_y": track.grid_y,
                "grid_major_divisions": track.grid_major_divisions,
                "grid_minor_divisions": track.grid_minor_divisions,
                "grid_alpha": track.grid_alpha,
                "grid_print": track.grid_print,
                "x_axis_label": track.x_axis_label,
            }
            for track in layout.tracks
        ],
    }


def layout_from_dict(data: object) -> TabletLayout:
    if not isinstance(data, dict):
        raise TabletLayoutFormatError("Компоновка планшета должна быть JSON-объектом")
    data = _migrate_layout(data)
    if data.get("version") != LAYOUT_FORMAT_VERSION:
        raise TabletLayoutFormatError("Неподдерживаемая версия компоновки планшета")
    raw_tracks = data.get("tracks")
    if not isinstance(raw_tracks, list):
        raise TabletLayoutFormatError("Поле 'tracks' должно быть списком")

    raw_depth_top = data.get("visible_depth_top")
    raw_depth_bottom = data.get("visible_depth_bottom")
    raw_cursor_depth = data.get("cursor_depth")
    raw_vertical_index_id = data.get("vertical_index_id")
    raw_annotation_scope_id = data.get("annotation_scope_id")
    # Version 21 layouts predate explicit caption provenance.  Treat those
    # payloads as localizable to preserve the runtime behavior introduced in
    # 0.7.93; newly created layouts always persist their explicit choice.
    raw_localize_factory_labels = data.get("localize_factory_labels", True)
    raw_vertical_ruler_scale = data.get("vertical_ruler_scale", {})
    if not isinstance(raw_vertical_ruler_scale, dict):
        raise TabletLayoutFormatError(
            "vertical_ruler_scale должен быть JSON-объектом"
        )
    raw_ruler_major_step = raw_vertical_ruler_scale.get("major_step")
    raw_ruler_minor_divisions = raw_vertical_ruler_scale.get(
        "minor_divisions", 5
    )
    if raw_ruler_major_step is not None and (
        not isinstance(raw_ruler_major_step, (int, float))
        or isinstance(raw_ruler_major_step, bool)
    ):
        raise TabletLayoutFormatError(
            "vertical_ruler_scale.major_step должен быть числом или null"
        )
    if (
        not isinstance(raw_ruler_minor_divisions, int)
        or isinstance(raw_ruler_minor_divisions, bool)
    ):
        raise TabletLayoutFormatError(
            "vertical_ruler_scale.minor_divisions должен быть целым числом"
        )
    try:
        vertical_ruler_scale = VerticalRulerScaleSettings(
            major_step=(
                float(raw_ruler_major_step)
                if raw_ruler_major_step is not None
                else None
            ),
            minor_divisions=raw_ruler_minor_divisions,
        )
    except ValueError as exc:
        raise TabletLayoutFormatError(
            "Некорректные настройки общей вертикальной шкалы"
        ) from exc
    if raw_vertical_index_id is not None and (
        not isinstance(raw_vertical_index_id, str) or not raw_vertical_index_id.strip()
    ):
        raise TabletLayoutFormatError("vertical_index_id должен быть строкой или null")
    if raw_annotation_scope_id is not None and (
        not isinstance(raw_annotation_scope_id, str)
        or not raw_annotation_scope_id.strip()
        or len(raw_annotation_scope_id) > 300
    ):
        raise TabletLayoutFormatError("annotation_scope_id должен быть строкой до 300 символов или null")
    if not isinstance(raw_localize_factory_labels, bool):
        raise TabletLayoutFormatError("localize_factory_labels должен быть логическим")
    for name, value in (
        ("visible_depth_top", raw_depth_top),
        ("visible_depth_bottom", raw_depth_bottom),
        ("cursor_depth", raw_cursor_depth),
    ):
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise TabletLayoutFormatError(f"{name} должен быть числом или null")
    try:
        layout = TabletLayout(
            visible_depth_top=float(raw_depth_top) if raw_depth_top is not None else None,
            visible_depth_bottom=(
                float(raw_depth_bottom) if raw_depth_bottom is not None else None
            ),
            cursor_depth=float(raw_cursor_depth) if raw_cursor_depth is not None else None,
            vertical_index_id=raw_vertical_index_id,
            annotation_scope_id=raw_annotation_scope_id,
            localize_factory_labels=raw_localize_factory_labels,
            vertical_ruler_scale=vertical_ruler_scale,
        )
    except ValueError as exc:
        raise TabletLayoutFormatError("Некорректный видимый интервал глубины") from exc
    for index, raw_track in enumerate(raw_tracks):
        try:
            track = _track_from_dict(raw_track)
            layout.add_track(track)
        except (KeyError, TypeError, ValueError) as exc:
            raise TabletLayoutFormatError(f"Некорректный трек с индексом {index}") from exc
    return layout


def _track_from_dict(data: object) -> TrackDefinition:
    if not isinstance(data, dict):
        raise TypeError("Трек должен быть JSON-объектом")

    track_id = data["track_id"]
    title = data["title"]
    group_title = data.get("group_title", "")
    title_orientation = data.get("title_orientation", "horizontal")
    title_position = data.get("title_position", "center")
    show_interval_labels = data.get("show_interval_labels", False)
    lba_label_orientation = data.get(
        "lba_label_orientation", "vertical_bottom_to_top"
    )
    calcimetry_label_orientation = data.get(
        "calcimetry_label_orientation", "horizontal"
    )
    show_description_borders = data.get("show_description_borders", True)
    raw_vertical_ruler = data.get("vertical_ruler", {})
    raw_mnemonics = data.get("curve_mnemonics", [])
    width = data.get("width", 260)
    visible = data.get("visible", True)
    locked = data.get("locked", False)
    raw_x_min = data.get("x_min")
    raw_x_max = data.get("x_max")
    raw_curve_styles = data.get("curve_styles", {})
    raw_curve_display = data.get("curve_display", {})
    raw_grid_x = data.get("grid_x", True)
    raw_grid_y = data.get("grid_y", True)
    raw_grid_major = data.get("grid_major_divisions", 5)
    raw_grid_minor = data.get("grid_minor_divisions", 5)
    raw_grid_alpha = data.get("grid_alpha", 0.2)
    raw_grid_print = data.get("grid_print", True)
    raw_x_axis_label = data.get("x_axis_label", "")
    if not isinstance(track_id, str) or not track_id.strip():
        raise TypeError("track_id должен быть непустой строкой")
    if not isinstance(title, str) or not title.strip():
        raise TypeError("title должен быть непустой строкой")
    if not isinstance(group_title, str):
        raise TypeError("group_title должен быть строкой")
    if not isinstance(title_orientation, str) or not isinstance(title_position, str):
        raise TypeError("Настройки заголовка трека должны быть строками")
    if not isinstance(lba_label_orientation, str):
        raise TypeError("Направление подписей ЛБА должно быть строкой")
    if not isinstance(calcimetry_label_orientation, str):
        raise TypeError("Направление подписей кальциметрии должно быть строкой")
    if not isinstance(show_interval_labels, bool):
        raise TypeError("show_interval_labels должен быть логическим")
    if not isinstance(show_description_borders, bool):
        raise TypeError("show_description_borders должен быть логическим")
    if not isinstance(raw_vertical_ruler, dict):
        raise TypeError("vertical_ruler должен быть JSON-объектом")
    vertical_ruler = VerticalRulerTrackSettings(
        mode=VerticalRulerMode(
            raw_vertical_ruler.get(
                "mode", VerticalRulerMode.AUTOMATIC.value
            )
        ),
        label_every_major=raw_vertical_ruler.get(
            "label_every_major", 1
        ),
        major_tick_every=raw_vertical_ruler.get(
            "major_tick_every", 1
        ),
        minor_tick_every=raw_vertical_ruler.get(
            "minor_tick_every", 1
        ),
    )
    if not isinstance(raw_mnemonics, list) or not all(
        isinstance(item, str) for item in raw_mnemonics
    ):
        raise TypeError("curve_mnemonics должен быть списком строк")
    if not isinstance(width, int) or isinstance(width, bool):
        raise TypeError("width должен быть целым числом")
    if not isinstance(visible, bool) or not isinstance(locked, bool):
        raise TypeError("visible и locked должны быть логическими значениями")
    for name, value in (("x_min", raw_x_min), ("x_max", raw_x_max)):
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise TypeError(f"{name} должен быть числом или null")
    if not isinstance(raw_curve_styles, dict):
        raise TypeError("curve_styles должен быть JSON-объектом")
    if not isinstance(raw_curve_display, dict):
        raise TypeError("curve_display должен быть JSON-объектом")
    curve_styles: dict[str, CurveStyle] = {}
    for mnemonic, raw_style in raw_curve_styles.items():
        if not isinstance(mnemonic, str) or not isinstance(raw_style, dict):
            raise TypeError("Некорректная настройка кривой")
        curve_styles[mnemonic] = CurveStyle(
            color=raw_style.get("color", "#2563eb"),
            width=raw_style.get("width", 1.5),
            line_style=CurveLineStyle(raw_style.get("line_style", CurveLineStyle.SOLID.value)),
        )
    curve_display: dict[str, CurveDisplaySettings] = {}
    for mnemonic, raw_settings in raw_curve_display.items():
        if not isinstance(mnemonic, str) or not isinstance(raw_settings, dict):
            raise TypeError("Некорректная настройка отображения кривой")
        raw_min = raw_settings.get("x_min")
        raw_max = raw_settings.get("x_max")
        curve_display[mnemonic] = CurveDisplaySettings(
            display_name=str(raw_settings.get("display_name") or ""),
            x_scale=XScale(raw_settings.get("x_scale", XScale.LINEAR.value)),
            x_min=float(raw_min) if raw_min is not None else None,
            x_max=float(raw_max) if raw_max is not None else None,
            unit_override=(
                str(raw_settings["unit_override"])
                if raw_settings.get("unit_override") is not None
                else None
            ),
            header_text_color=str(raw_settings.get("header_text_color", "#0f172a")),
            header_line_color=(
                str(raw_settings["header_line_color"])
                if raw_settings.get("header_line_color") is not None
                else None
            ),
        )
    if not isinstance(raw_grid_x, bool) or not isinstance(raw_grid_y, bool):
        raise TypeError("grid_x и grid_y должны быть логическими значениями")
    for name, value in (
        ("grid_major_divisions", raw_grid_major),
        ("grid_minor_divisions", raw_grid_minor),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} должен быть целым числом")
    if not isinstance(raw_grid_alpha, (int, float)) or isinstance(raw_grid_alpha, bool):
        raise TypeError("grid_alpha должен быть числом")
    if not isinstance(raw_grid_print, bool):
        raise TypeError("grid_print должен быть логическим значением")
    if not isinstance(raw_x_axis_label, str):
        raise TypeError("x_axis_label должен быть строкой")

    return TrackDefinition(
        track_id=track_id,
        title=title,
        kind=TrackKind(data["kind"]),
        group_title=group_title,
        title_orientation=title_orientation,
        title_position=title_position,
        show_interval_labels=show_interval_labels,
        lba_label_orientation=lba_label_orientation,
        calcimetry_label_orientation=calcimetry_label_orientation,
        show_description_borders=show_description_borders,
        vertical_ruler=vertical_ruler,
        curve_mnemonics=list(raw_mnemonics),
        width=width,
        visible=visible,
        locked=locked,
        x_scale=XScale(data.get("x_scale", XScale.LINEAR.value)),
        x_min=float(raw_x_min) if raw_x_min is not None else None,
        x_max=float(raw_x_max) if raw_x_max is not None else None,
        curve_styles=curve_styles,
        curve_display=curve_display,
        grid_x=raw_grid_x,
        grid_y=raw_grid_y,
        grid_major_divisions=raw_grid_major,
        grid_minor_divisions=raw_grid_minor,
        grid_alpha=float(raw_grid_alpha),
        grid_print=raw_grid_print,
        x_axis_label=raw_x_axis_label,
    )


def _migrate_layout(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("version")
    if version == LAYOUT_FORMAT_VERSION:
        return data
    if version not in (
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23
    ):
        raise TabletLayoutFormatError("Неподдерживаемая версия компоновки планшета")
    migrated = deepcopy(data)
    if version == 1:
        migrated["version"] = 2
        tracks = migrated.get("tracks")
        if isinstance(tracks, list):
            for track in tracks:
                if isinstance(track, dict):
                    track.setdefault("x_scale", XScale.LINEAR.value)
                    track.setdefault("x_min", None)
                    track.setdefault("x_max", None)
    migrated["version"] = 3
    migrated.setdefault("visible_depth_top", None)
    migrated.setdefault("visible_depth_bottom", None)
    migrated["version"] = 4
    tracks = migrated.get("tracks")
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault("curve_styles", {})
    migrated["version"] = 5
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault("grid_x", True)
                track.setdefault("grid_y", True)
                track.setdefault("grid_alpha", 0.2)
    migrated["version"] = 6
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault("x_axis_label", "")
    migrated["version"] = 7
    migrated.setdefault("cursor_depth", None)
    migrated["version"] = 8
    migrated.setdefault("vertical_index_id", None)
    migrated["version"] = 9
    tracks = migrated.get("tracks")
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault("curve_display", {})
    migrated["version"] = 10
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault("group_title", "")
    migrated["version"] = 11
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault("title_orientation", "horizontal")
                track.setdefault("title_position", "center")
    migrated["version"] = 12
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault("show_interval_labels", False)
    migrated["version"] = 13
    migrated.setdefault("annotation_scope_id", None)
    migrated["version"] = 14
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault("grid_major_divisions", 5)
                track.setdefault("grid_minor_divisions", 5)
                track.setdefault("grid_print", True)
    migrated["version"] = 15
    if isinstance(tracks, list):
        for track in tracks:
            if not isinstance(track, dict):
                continue
            display = track.get("curve_display", {})
            if isinstance(display, dict):
                for settings in display.values():
                    if isinstance(settings, dict):
                        settings.setdefault("header_text_color", "#0f172a")
                        settings.setdefault("header_line_color", None)
    migrated["version"] = 16
    if isinstance(tracks, list):
        for track in tracks:
            if not isinstance(track, dict):
                continue
            display = track.get("curve_display", {})
            if isinstance(display, dict):
                for settings in display.values():
                    if isinstance(settings, dict):
                        settings.setdefault("unit_override", None)
    migrated["version"] = 17
    if isinstance(tracks, list):
        for track in tracks:
            if not isinstance(track, dict):
                continue
            try:
                kind = TrackKind(str(track.get("kind", TrackKind.CURVE.value)))
            except ValueError:
                continue
            raw_width = track.get("width", 260)
            if isinstance(raw_width, int) and not isinstance(raw_width, bool):
                track["width"] = compact_track_width(kind, raw_width)
    migrated["version"] = 18
    if isinstance(tracks, list):
        # Version 19 makes every previously saved tablet/form layout linear by
        # default.  This is a one-time migration: users may explicitly switch a
        # curve back to logarithmic mode after the project has been upgraded.
        for track in tracks:
            if not isinstance(track, dict):
                continue
            _migrate_scale_payload_to_linear(track)
            display = track.get("curve_display")
            if isinstance(display, dict):
                for settings in display.values():
                    if isinstance(settings, dict):
                        _migrate_scale_payload_to_linear(settings)
    migrated["version"] = 20
    if isinstance(tracks, list):
        # Version 21 preserves vertical captions for long compact columns and
        # changes the short LBA caption back to horizontal in existing layouts.
        for track in tracks:
            if not isinstance(track, dict):
                continue
            try:
                kind = TrackKind(str(track.get("kind", TrackKind.CURVE.value)))
            except ValueError:
                continue
            if kind not in COMPACT_TRACK_KINDS:
                continue
            orientation = compact_track_title_orientation(kind)
            if kind is TrackKind.LBA:
                track["title_orientation"] = orientation
            elif str(track.get("title_orientation", "horizontal")) == "horizontal":
                track["title_orientation"] = orientation
            track.setdefault("title_position", compact_track_title_position(kind))
    migrated["version"] = 22
    migrated.setdefault(
        "vertical_ruler_scale",
        {"major_step": None, "minor_divisions": 5},
    )
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault(
                    "vertical_ruler",
                    {
                        "mode": VerticalRulerMode.AUTOMATIC.value,
                        "label_every_major": 1,
                        "major_tick_every": 1,
                        "minor_tick_every": 1,
                    },
                )
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault(
                    "lba_label_orientation", "vertical_bottom_to_top"
                )
                track.setdefault("calcimetry_label_orientation", "horizontal")
                track.setdefault("show_description_borders", True)
    migrated["version"] = LAYOUT_FORMAT_VERSION
    return migrated


def _migrate_scale_payload_to_linear(payload: dict[str, Any]) -> None:
    """Convert one legacy track/curve scale payload to a linear default."""

    if payload.get("x_scale") != XScale.LOGARITHMIC.value:
        payload.setdefault("x_scale", XScale.LINEAR.value)
        return
    payload["x_scale"] = XScale.LINEAR.value
    minimum = payload.get("x_min")
    maximum = payload.get("x_max")
    if (
        isinstance(minimum, (int, float))
        and not isinstance(minimum, bool)
        and isinstance(maximum, (int, float))
        and not isinstance(maximum, bool)
        and minimum > 0
        and maximum > 0
    ):
        payload["x_min"] = 0.0
