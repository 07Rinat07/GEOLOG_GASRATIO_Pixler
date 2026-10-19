from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import TYPE_CHECKING

from geoworkbench.domain.report_composition import InterpretationReportComposition
from geoworkbench.services.lba_observations import has_recorded_lba

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


def geology_track_settings_from_composition(
    composition: InterpretationReportComposition,
) -> InterpretationGeologyTrackSettings:
    return InterpretationGeologyTrackSettings(
        cuttings=GeologyTrackVisibility(composition.cuttings.value),
        lba=GeologyTrackVisibility(composition.lba.value),
    )


def resolve_geology_track_kinds(
    geology: "InterpretationGeologySnapshot | None",
    top_depth: float,
    bottom_depth: float,
    settings: InterpretationGeologyTrackSettings,
) -> tuple[str, ...]:
    visible = visible_geology_samples(geology, top_depth, bottom_depth)
    has_cuttings = any(sample.components for sample in visible)
    has_lba = any(has_recorded_lba(sample) for sample in visible)
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
    visible = visible_geology_samples(geology, top_depth, bottom_depth)
    has_cuttings = any(sample.components for sample in visible)
    has_lba = any(has_recorded_lba(sample) for sample in visible)
    empty: list[str] = []
    if settings.cuttings is GeologyTrackVisibility.SHOW and not has_cuttings:
        empty.append("cuttings")
    if settings.lba is GeologyTrackVisibility.SHOW and not has_lba:
        empty.append("lba")
    return tuple(empty)


def visible_geology_samples(
    geology: "InterpretationGeologySnapshot | None",
    top_depth: float,
    bottom_depth: float,
) -> tuple["FrozenCuttingsSample", ...]:
    """Select only finite samples with positive overlap, preserving source order.

    A sample merely touching a page edge has no drawable interval and must
    not enable Auto tracks or add symbols to that page's legend.
    """
    if geology is None or not (
        isfinite(top_depth) and isfinite(bottom_depth) and top_depth < bottom_depth
    ):
        return ()
    return tuple(
        sample
        for sample in geology.samples
        if isfinite(sample.top_depth) and isfinite(sample.bottom_depth)
        and sample.top_depth < sample.bottom_depth
        and sample.bottom_depth > top_depth and sample.top_depth < bottom_depth
    )


__all__ = [
    "DEFAULT_INTERPRETATION_GEOLOGY_TRACK_SETTINGS",
    "GeologyTrackVisibility",
    "InterpretationGeologyTrackSettings",
    "forced_empty_geology_tracks",
    "geology_track_settings_from_composition",
    "resolve_geology_track_kinds",
    "visible_geology_samples",
]
