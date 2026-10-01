from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geoworkbench.printing.geology_track_rendering import FrozenCuttingsSample
    from geoworkbench.printing.hydrocarbon_interpretation_geology import (
        InterpretationGeologySnapshot,
    )


class GeologyTrackVisibility(str, Enum):
    AUTO = "auto"
    SHOW = "show"
    HIDE = "hide"


@dataclass(frozen=True, slots=True)
class InterpretationGeologyTrackSettings:
    cuttings: GeologyTrackVisibility = GeologyTrackVisibility.AUTO
    lba: GeologyTrackVisibility = GeologyTrackVisibility.AUTO


DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS = InterpretationGeologyTrackSettings()


def resolve_geology_track_kinds(
    geology: "InterpretationGeologySnapshot | None",
    top_depth: float,
    bottom_depth: float,
    settings: InterpretationGeologyTrackSettings,
) -> tuple[str, ...]:
    visible = _visible_samples(geology, top_depth, bottom_depth)
    has_cuttings = any(sample.components for sample in visible)
    has_lba = any(
        value not in (None, "")
        for sample in visible
        for value in (
            sample.lba_group,
            sample.lba_type_id,
            sample.lba_intensity,
            sample.lba_color,
            sample.lba_distribution,
            sample.lba_cut,
            sample.lba_description,
        )
    )
    tracks: list[str] = []
    if settings.cuttings is GeologyTrackVisibility.SHOW or (
        settings.cuttings is GeologyTrackVisibility.AUTO and has_cuttings
    ):
        tracks.append("cuttings")
    if settings.lba is GeologyTrackVisibility.SHOW or (
        settings.lba is GeologyTrackVisibility.AUTO and has_lba
    ):
        tracks.append("lba")
    return tuple(tracks)


def forced_empty_geology_tracks(
    geology: "InterpretationGeologySnapshot | None",
    top_depth: float,
    bottom_depth: float,
    settings: InterpretationGeologyTrackSettings,
) -> tuple[str, ...]:
    visible = _visible_samples(geology, top_depth, bottom_depth)
    has_cuttings = any(sample.components for sample in visible)
    has_lba = any(
        value not in (None, "")
        for sample in visible
        for value in (
            sample.lba_group,
            sample.lba_type_id,
            sample.lba_intensity,
            sample.lba_color,
            sample.lba_distribution,
            sample.lba_cut,
            sample.lba_description,
        )
    )
    empty: list[str] = []
    if settings.cuttings is GeologyTrackVisibility.SHOW and not has_cuttings:
        empty.append("cuttings")
    if settings.lba is GeologyTrackVisibility.SHOW and not has_lba:
        empty.append("lba")
    return tuple(empty)


def _visible_samples(
    geology: "InterpretationGeologySnapshot | None",
    top_depth: float,
    bottom_depth: float,
) -> tuple["FrozenCuttingsSample", ...]:
    if geology is None:
        return ()
    return tuple(
        sample
        for sample in geology.samples
        if sample.bottom_depth >= top_depth and sample.top_depth <= bottom_depth
    )


__all__ = [
    "DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS",
    "GeologyTrackVisibility",
    "InterpretationGeologyTrackSettings",
    "forced_empty_geology_tracks",
    "resolve_geology_track_kinds",
]
