from __future__ import annotations

import pytest

from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerKind,
    VerticalRulerMode,
    VerticalRulerScaleSettings,
    VerticalRulerTrackSettings,
    build_vertical_ruler_layout,
    visible_vertical_ruler_ticks,
)


def test_manual_frequency_is_applied_once_to_shared_depth_layout() -> None:
    layout = build_vertical_ruler_layout(
        1703.28,
        1753.28,
        pixel_height=900,
        kind=VerticalRulerKind.DEPTH,
        unit="м",
        settings=VerticalRulerScaleSettings(
            major_step=10.0,
            minor_divisions=5,
        ),
    )

    assert layout.major_step == 10.0
    assert layout.minor_step == 2.0
    assert [tick.label for tick in layout.ticks if tick.label][:2] == ["1710", "1720"]


def test_column_can_disable_inner_ruler_without_changing_shared_layout() -> None:
    layout = build_vertical_ruler_layout(
        1000.0,
        1050.0,
        pixel_height=600,
        kind=VerticalRulerKind.DEPTH,
    )
    original_values = tuple(tick.value for tick in layout.ticks)

    visible = visible_vertical_ruler_ticks(
        layout,
        VerticalRulerTrackSettings(mode=VerticalRulerMode.OFF),
    )

    assert visible == ()
    assert original_values == tuple(tick.value for tick in layout.ticks)


def test_column_frequency_only_filters_shared_tick_subset() -> None:
    layout = build_vertical_ruler_layout(
        1000.0,
        1050.0,
        pixel_height=900,
        kind=VerticalRulerKind.DEPTH,
        settings=VerticalRulerScaleSettings(major_step=5.0, minor_divisions=5),
    )
    settings = VerticalRulerTrackSettings(
        mode=VerticalRulerMode.LABELS_AND_TICKS,
        label_every_major=2,
        major_tick_every=1,
        minor_tick_every=2,
    )

    visible = visible_vertical_ruler_ticks(layout, settings)
    shared_values = {tick.value for tick in layout.ticks}

    assert visible
    assert all(tick.value in shared_values for tick in visible)
    labels = [tick.label for tick in visible if tick.label]
    assert labels[:2] == ["1000", "1010"]


def test_ticks_only_mode_never_outputs_numeric_labels() -> None:
    layout = build_vertical_ruler_layout(
        0.0,
        50.0,
        pixel_height=600,
        kind=VerticalRulerKind.DEPTH,
    )

    visible = visible_vertical_ruler_ticks(
        layout,
        VerticalRulerTrackSettings(mode=VerticalRulerMode.TICKS_ONLY),
    )

    assert visible
    assert all(not tick.label for tick in visible)


@pytest.mark.parametrize(
    "settings",
    [
        VerticalRulerScaleSettings(major_step=1.0, minor_divisions=1),
        VerticalRulerScaleSettings(major_step=20.0, minor_divisions=10),
        VerticalRulerTrackSettings(label_every_major=1),
        VerticalRulerTrackSettings(major_tick_every=20, minor_tick_every=20),
    ],
)
def test_supported_settings_are_constructible(settings: object) -> None:
    assert settings is not None


@pytest.mark.parametrize(
    "factory",
    [
        lambda: VerticalRulerScaleSettings(major_step=0.0),
        lambda: VerticalRulerScaleSettings(minor_divisions=0),
        lambda: VerticalRulerTrackSettings(label_every_major=0),
        lambda: VerticalRulerTrackSettings(major_tick_every=21),
    ],
)
def test_invalid_frequency_settings_fail_closed(factory) -> None:
    with pytest.raises(ValueError):
        factory()
