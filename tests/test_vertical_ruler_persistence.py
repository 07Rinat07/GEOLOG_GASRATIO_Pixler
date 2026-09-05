from __future__ import annotations

import pytest

from geoworkbench.tablet.layout_codec import (
    LAYOUT_FORMAT_VERSION,
    TabletLayoutFormatError,
    layout_from_dict,
    layout_to_dict,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerMode,
    VerticalRulerScaleSettings,
    VerticalRulerTrackSettings,
)


def test_vertical_ruler_settings_round_trip_with_layout_v23() -> None:
    track = TrackDefinition(
        track_id="gas",
        title="Газы",
        kind=TrackKind.GAS,
        vertical_ruler=VerticalRulerTrackSettings(
            mode=VerticalRulerMode.TICKS_ONLY,
            label_every_major=2,
            major_tick_every=2,
            minor_tick_every=3,
        ),
    )
    layout = TabletLayout(
        tracks=[track],
        vertical_ruler_scale=VerticalRulerScaleSettings(
            major_step=10.0,
            minor_divisions=5,
        ),
    )

    payload = layout_to_dict(layout)
    restored = layout_from_dict(payload)

    assert payload["version"] == LAYOUT_FORMAT_VERSION == 25
    assert payload["vertical_ruler_scale"] == {
        "major_step": 10.0,
        "minor_divisions": 5,
    }
    assert restored.vertical_ruler_scale == layout.vertical_ruler_scale
    assert restored.tracks[0].vertical_ruler == track.vertical_ruler


def test_layout_v21_migrates_to_safe_shared_ruler_defaults() -> None:
    restored = layout_from_dict(
        {
            "version": 21,
            "tracks": [
                {
                    "track_id": "curve",
                    "title": "Кривые",
                    "kind": "curve",
                }
            ],
        }
    )

    assert restored.vertical_ruler_scale == VerticalRulerScaleSettings()
    assert restored.tracks[0].vertical_ruler == VerticalRulerTrackSettings()
    migrated = layout_to_dict(restored)
    assert migrated["version"] == 25


def test_layout_rejects_invalid_global_ruler_frequency() -> None:
    payload = layout_to_dict(TabletLayout())
    payload["vertical_ruler_scale"]["major_step"] = 0.0

    with pytest.raises(TabletLayoutFormatError):
        layout_from_dict(payload)


def test_layout_rejects_invalid_per_track_ruler_mode() -> None:
    payload = layout_to_dict(
        TabletLayout(
            tracks=[
                TrackDefinition(
                    track_id="gas",
                    title="Газы",
                    kind=TrackKind.GAS,
                )
            ]
        )
    )
    payload["tracks"][0]["vertical_ruler"]["mode"] = "broken"

    with pytest.raises(TabletLayoutFormatError):
        layout_from_dict(payload)


def test_layout_setters_report_only_material_changes() -> None:
    layout = TabletLayout(
        tracks=[
            TrackDefinition(
                track_id="gas",
                title="Газы",
                kind=TrackKind.GAS,
            )
        ]
    )
    track_settings = VerticalRulerTrackSettings(
        mode=VerticalRulerMode.OFF
    )
    scale_settings = VerticalRulerScaleSettings(
        major_step=5.0,
        minor_divisions=5,
    )

    assert layout.set_track_vertical_ruler("gas", track_settings)
    assert not layout.set_track_vertical_ruler("gas", track_settings)
    assert layout.set_vertical_ruler_scale(scale_settings)
    assert not layout.set_vertical_ruler_scale(scale_settings)
