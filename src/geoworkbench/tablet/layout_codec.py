from __future__ import annotations

from typing import Any

from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind


LAYOUT_FORMAT_VERSION = 1


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
            }
            for track in layout.tracks
        ],
    }


def layout_from_dict(data: object) -> TabletLayout:
    if not isinstance(data, dict):
        raise TabletLayoutFormatError("Компоновка планшета должна быть JSON-объектом")
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

    return TrackDefinition(
        track_id=track_id,
        title=title,
        kind=TrackKind(data["kind"]),
        curve_mnemonics=list(raw_mnemonics),
        width=width,
        visible=visible,
        locked=locked,
    )
