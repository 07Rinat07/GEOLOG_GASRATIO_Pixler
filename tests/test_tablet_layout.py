import pytest

from geoworkbench.tablet.layout_codec import (
    TabletLayoutFormatError,
    layout_from_dict,
    layout_to_dict,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind, XScale


def make_layout() -> TabletLayout:
    return TabletLayout(
        [
            TrackDefinition("depth", "Глубина", TrackKind.DEPTH, width=120, locked=True),
            TrackDefinition(
                "gas",
                "Газ",
                TrackKind.GAS,
                curve_mnemonics=["C1", "C2"],
                width=360,
            ),
        ]
    )


def test_layout_updates_track_properties() -> None:
    layout = make_layout()

    layout.set_track_width("gas", 420)
    layout.set_track_visible("gas", False)

    assert layout.track_by_id("gas").width == 420
    assert [track.track_id for track in layout.visible_tracks()] == ["depth"]


def test_layout_rejects_invalid_width_without_mutation() -> None:
    layout = make_layout()

    with pytest.raises(ValueError):
        layout.set_track_width("gas", 79)

    assert layout.track_by_id("gas").width == 360


def test_layout_codec_round_trip_preserves_track_settings() -> None:
    source = make_layout()
    source.set_track_visible("gas", False)
    source.set_track_x_range("gas", 0.1, 1000.0)
    source.set_track_x_scale("gas", XScale.LOGARITHMIC)
    source.set_visible_depth(1200.0, 1300.0)

    restored = layout_from_dict(layout_to_dict(source))

    assert restored == source
    assert restored.tracks[0].kind is TrackKind.DEPTH
    assert restored.visible_depth_top == 1200.0
    assert restored.visible_depth_bottom == 1300.0


def test_layout_codec_migrates_v1_x_settings_to_linear_auto_range() -> None:
    payload = {
        "version": 1,
        "tracks": [
            {
                "track_id": "curve",
                "title": "Curve",
                "kind": "curve",
                "width": 200,
            }
        ],
    }

    restored = layout_from_dict(payload)

    track = restored.track_by_id("curve")
    assert track.x_scale is XScale.LINEAR
    assert track.x_min is None
    assert track.x_max is None
    assert payload["version"] == 1


def test_layout_codec_migrates_v2_to_auto_depth_range() -> None:
    payload = {
        "version": 2,
        "tracks": [],
    }

    restored = layout_from_dict(payload)

    assert restored.visible_depth_top is None
    assert restored.visible_depth_bottom is None
    assert payload["version"] == 2


@pytest.mark.parametrize(
    ("top", "bottom"),
    [(100.0, 100.0), (101.0, 100.0), (None, 100.0), (float("nan"), 100.0)],
)
def test_layout_rejects_invalid_visible_depth(
    top: float | None,
    bottom: float | None,
) -> None:
    with pytest.raises(ValueError):
        TabletLayout(visible_depth_top=top, visible_depth_bottom=bottom)


@pytest.mark.parametrize(
    ("scale", "minimum", "maximum"),
    [
        (XScale.LINEAR, 1.0, 1.0),
        (XScale.LINEAR, 2.0, 1.0),
        (XScale.LOGARITHMIC, 0.0, 10.0),
        (XScale.LOGARITHMIC, -1.0, 10.0),
        (XScale.LINEAR, None, 10.0),
    ],
)
def test_track_rejects_invalid_x_range(
    scale: XScale,
    minimum: float | None,
    maximum: float | None,
) -> None:
    with pytest.raises(ValueError):
        TrackDefinition(
            "curve",
            "Curve",
            TrackKind.CURVE,
            x_scale=scale,
            x_min=minimum,
            x_max=maximum,
        )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"version": 99, "tracks": []},
        {"version": 1, "tracks": "not-a-list"},
        {
            "version": 1,
            "tracks": [
                {
                    "track_id": "bad",
                    "title": "Bad",
                    "kind": "unknown",
                    "width": 100,
                }
            ],
        },
        {
            "version": 1,
            "tracks": [
                {
                    "track_id": "bad",
                    "title": "Bad",
                    "kind": "curve",
                    "width": True,
                }
            ],
        },
    ],
)
def test_layout_codec_rejects_invalid_payload(payload: object) -> None:
    with pytest.raises(TabletLayoutFormatError):
        layout_from_dict(payload)


def test_layout_codec_rejects_duplicate_track_ids() -> None:
    track = layout_to_dict(make_layout())["tracks"][0]

    with pytest.raises(TabletLayoutFormatError):
        layout_from_dict({"version": 1, "tracks": [track, track]})
