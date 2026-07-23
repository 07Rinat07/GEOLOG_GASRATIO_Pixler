from __future__ import annotations

from geoworkbench.tablet.grid_renderer import (
    GridSettings,
    engineering_tick_levels,
    normalized_grid_lines,
)
from geoworkbench.tablet.models import TrackDefinition, TrackKind


def test_engineering_levels_keep_major_and_intermediate_spacing_stable() -> None:
    assert engineering_tick_levels(1000.0, 1100.0, 4, 10) == (
        (25.0, 1000.0),
        (2.5, 1000.0),
    )
    assert engineering_tick_levels(10.0, 0.0, 5, 1) == ((2.0, 0.0),)


def test_normalized_grid_lines_are_shared_major_minor_positions() -> None:
    lines = normalized_grid_lines(2, 2)

    assert [(line.fraction, line.major) for line in lines] == [
        (0.0, True),
        (0.25, False),
        (0.5, True),
        (0.75, False),
        (1.0, True),
    ]


def test_screen_settings_preserve_saved_track_configuration() -> None:
    track = TrackDefinition(
        "gas",
        "Gas",
        TrackKind.GAS,
        grid_x=False,
        grid_y=True,
        grid_major_divisions=4,
        grid_minor_divisions=10,
        grid_alpha=0.35,
        grid_print=False,
    )

    assert GridSettings.from_track(track) == GridSettings(False, True, 4, 10, 0.35)
