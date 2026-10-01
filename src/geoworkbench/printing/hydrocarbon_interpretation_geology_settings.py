from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GeologyTrackVisibility(str, Enum):
    AUTO = "auto"
    SHOW = "show"
    HIDE = "hide"


@dataclass(frozen=True, slots=True)
class InterpretationGeologyTrackSettings:
    cuttings: GeologyTrackVisibility = GeologyTrackVisibility.AUTO
    lba: GeologyTrackVisibility = GeologyTrackVisibility.AUTO


DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS = InterpretationGeologyTrackSettings()


__all__ = [
    "DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS",
    "GeologyTrackVisibility",
    "InterpretationGeologyTrackSettings",
]
