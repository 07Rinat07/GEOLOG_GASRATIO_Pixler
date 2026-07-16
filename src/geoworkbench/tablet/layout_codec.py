from __future__ import annotations

from copy import deepcopy
from typing import Any

from geoworkbench.tablet.models import (
    CurveLineStyle,
    CurveStyle,
    TabletLayout,
    TrackDefinition,
    TrackKind,
    XScale,
)


LAYOUT_FORMAT_VERSION = 6


class TabletLayoutFormatError(ValueError):
    """Raised when persisted tablet layout data is invalid or unsupported."""


def layout_to_dict(layout: TabletLayout) -> dict[str, Any]:
    return {
        "version": LAYOUT_FORMAT_VERSION,
        "visible_depth_top": layout.visible_depth_top,
        "visible_depth_bottom": layout.visible_depth_bottom,
        "tracks": [
            {
                "track_id": track.track_id,
                "title": track.title,
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
                "grid_x": track.grid_x,
                "grid_y": track.grid_y,
                "grid_alpha": track.grid_alpha,
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
    for name, value in (
        ("visible_depth_top", raw_depth_top),
        ("visible_depth_bottom", raw_depth_bottom),
    ):
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise TabletLayoutFormatError(f"{name} должен быть числом или null")
    try:
        layout = TabletLayout(
            visible_depth_top=float(raw_depth_top) if raw_depth_top is not None else None,
            visible_depth_bottom=(
                float(raw_depth_bottom) if raw_depth_bottom is not None else None
            ),
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
    raw_mnemonics = data.get("curve_mnemonics", [])
    width = data.get("width", 260)
    visible = data.get("visible", True)
    locked = data.get("locked", False)
    raw_x_min = data.get("x_min")
    raw_x_max = data.get("x_max")
    raw_curve_styles = data.get("curve_styles", {})
    raw_grid_x = data.get("grid_x", True)
    raw_grid_y = data.get("grid_y", True)
    raw_grid_alpha = data.get("grid_alpha", 0.2)
    raw_x_axis_label = data.get("x_axis_label", "")
    if not isinstance(track_id, str) or not track_id.strip():
        raise TypeError("track_id должен быть непустой строкой")
    if not isinstance(title, str) or not title.strip():
        raise TypeError("title должен быть непустой строкой")
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
    curve_styles: dict[str, CurveStyle] = {}
    for mnemonic, raw_style in raw_curve_styles.items():
        if not isinstance(mnemonic, str) or not isinstance(raw_style, dict):
            raise TypeError("Некорректная настройка кривой")
        curve_styles[mnemonic] = CurveStyle(
            color=raw_style.get("color", "#2563eb"),
            width=raw_style.get("width", 1.5),
            line_style=CurveLineStyle(
                raw_style.get("line_style", CurveLineStyle.SOLID.value)
            ),
        )
    if not isinstance(raw_grid_x, bool) or not isinstance(raw_grid_y, bool):
        raise TypeError("grid_x и grid_y должны быть логическими значениями")
    if not isinstance(raw_grid_alpha, (int, float)) or isinstance(raw_grid_alpha, bool):
        raise TypeError("grid_alpha должен быть числом")
    if not isinstance(raw_x_axis_label, str):
        raise TypeError("x_axis_label должен быть строкой")

    return TrackDefinition(
        track_id=track_id,
        title=title,
        kind=TrackKind(data["kind"]),
        curve_mnemonics=list(raw_mnemonics),
        width=width,
        visible=visible,
        locked=locked,
        x_scale=XScale(data.get("x_scale", XScale.LINEAR.value)),
        x_min=float(raw_x_min) if raw_x_min is not None else None,
        x_max=float(raw_x_max) if raw_x_max is not None else None,
        curve_styles=curve_styles,
        grid_x=raw_grid_x,
        grid_y=raw_grid_y,
        grid_alpha=float(raw_grid_alpha),
        x_axis_label=raw_x_axis_label,
    )


def _migrate_layout(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("version")
    if version == LAYOUT_FORMAT_VERSION:
        return data
    if version not in (1, 2, 3, 4, 5):
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
    return migrated
