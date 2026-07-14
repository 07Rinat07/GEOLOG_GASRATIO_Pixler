import pytest

from geoworkbench.tablet.layout_codec import (
    TabletLayoutFormatError,
    layout_from_dict,
    layout_to_dict,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind


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

    restored = layout_from_dict(layout_to_dict(source))

    assert restored == source
    assert restored.tracks[0].kind is TrackKind.DEPTH


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
