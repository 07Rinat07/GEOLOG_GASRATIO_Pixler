from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite


class TrackKind(StrEnum):
    DEPTH = "depth"
    CURVE = "curve"
    GAS = "gas"
    LITHOLOGY = "lithology"
    CUTTINGS = "cuttings"
    STRATIGRAPHY = "stratigraphy"
    TEXT = "text"


class XScale(StrEnum):
    LINEAR = "linear"
    LOGARITHMIC = "logarithmic"


@dataclass(slots=True)
class TrackDefinition:
    track_id: str
    title: str
    kind: TrackKind
    curve_mnemonics: list[str] = field(default_factory=list)
    width: int = 260
    visible: bool = True
    locked: bool = False
    x_scale: XScale = XScale.LINEAR
    x_min: float | None = None
    x_max: float | None = None

    def __post_init__(self) -> None:
        if self.width < 80:
            raise ValueError("Ширина трека должна быть не меньше 80 px")
        self._validate_x_settings(self.x_scale, self.x_min, self.x_max)

    def set_x_scale(self, scale: XScale) -> None:
        self._validate_x_settings(scale, self.x_min, self.x_max)
        self.x_scale = scale

    def set_x_range(self, minimum: float | None, maximum: float | None) -> None:
        self._validate_x_settings(self.x_scale, minimum, maximum)
        self.x_min = minimum
        self.x_max = maximum

    @staticmethod
    def _validate_x_settings(
        scale: XScale,
        minimum: float | None,
        maximum: float | None,
    ) -> None:
        if (minimum is None) != (maximum is None):
            raise ValueError("Минимум и максимум диапазона должны задаваться вместе")
        if minimum is None or maximum is None:
            return
        if not isfinite(minimum) or not isfinite(maximum):
            raise ValueError("Границы диапазона должны быть конечными числами")
        if minimum >= maximum:
            raise ValueError("Минимум диапазона должен быть меньше максимума")
        if scale is XScale.LOGARITHMIC and minimum <= 0:
            raise ValueError("Логарифмический диапазон должен быть положительным")


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

    def track_by_id(self, track_id: str) -> TrackDefinition:
        for track in self.tracks:
            if track.track_id == track_id:
                return track
        raise KeyError(track_id)

    def move_track(self, track_id: str, target_index: int) -> None:
        track = self.remove_track(track_id)
        target_index = max(0, min(target_index, len(self.tracks)))
        self.tracks.insert(target_index, track)

    def visible_tracks(self) -> list[TrackDefinition]:
        return [track for track in self.tracks if track.visible]

    def set_track_width(self, track_id: str, width: int) -> None:
        if width < 80:
            raise ValueError("Ширина трека должна быть не меньше 80 px")
        self.track_by_id(track_id).width = width

    def set_track_visible(self, track_id: str, visible: bool) -> None:
        self.track_by_id(track_id).visible = visible

    def set_track_x_scale(self, track_id: str, scale: XScale) -> None:
        self.track_by_id(track_id).set_x_scale(scale)

    def set_track_x_range(
        self,
        track_id: str,
        minimum: float | None,
        maximum: float | None,
    ) -> None:
        self.track_by_id(track_id).set_x_range(minimum, maximum)
