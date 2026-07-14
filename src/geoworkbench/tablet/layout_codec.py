from __future__ import annotations

from typing import Any

from copy import deepcopy

from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind, XScale


LAYOUT_FORMAT_VERSION = 2


class TabletLayoutFormatError(ValueError):
    """Raised when persisted tablet layout data is invalid or unsupported."""


def layout_to_dict(layout: TabletLayout) -> dict[str, Any]:
    return {
        "version": LAYOUT_FORMAT_VERSION,
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

    layout = TabletLayout()
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
    )


def _migrate_layout(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("version")
    if version == LAYOUT_FORMAT_VERSION:
        return data
    if version != 1:
        raise TabletLayoutFormatError("Неподдерживаемая версия компоновки планшета")
    migrated = deepcopy(data)
    migrated["version"] = 2
    tracks = migrated.get("tracks")
    if isinstance(tracks, list):
        for track in tracks:
            if isinstance(track, dict):
                track.setdefault("x_scale", XScale.LINEAR.value)
                track.setdefault("x_min", None)
                track.setdefault("x_max", None)
    return migrated
