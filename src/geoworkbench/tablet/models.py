from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TrackKind(StrEnum):
    DEPTH = "depth"
    CURVE = "curve"
    GAS = "gas"
    LITHOLOGY = "lithology"
    CUTTINGS = "cuttings"
    STRATIGRAPHY = "stratigraphy"
    TEXT = "text"


@dataclass(slots=True)
class TrackDefinition:
    track_id: str
    title: str
    kind: TrackKind
    curve_mnemonics: list[str] = field(default_factory=list)
    width: int = 260
    visible: bool = True
    locked: bool = False

    def __post_init__(self) -> None:
        if self.width < 80:
            raise ValueError("Ширина трека должна быть не меньше 80 px")


@dataclass(slots=True)
class TabletLayout:
    tracks: list[TrackDefinition] = field(default_factory=list)

    def add_track(self, track: TrackDefinition, index: int | None = None) -> None:
        if any(existing.track_id == track.track_id for existing in self.tracks):
            raise ValueError(f"Трек уже существует: {track.track_id}")
        if index is None:
            self.tracks.append(track)
        else:
            self.tracks.insert(index, track)

    def remove_track(self, track_id: str) -> TrackDefinition:
        for index, track in enumerate(self.tracks):
            if track.track_id == track_id:
                return self.tracks.pop(index)
        raise KeyError(track_id)

    def move_track(self, track_id: str, target_index: int) -> None:
        track = self.remove_track(track_id)
        target_index = max(0, min(target_index, len(self.tracks)))
        self.tracks.insert(target_index, track)

    def visible_tracks(self) -> list[TrackDefinition]:
        return [track for track in self.tracks if track.visible]
