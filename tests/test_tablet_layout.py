import pytest

from geoworkbench.tablet.layout_codec import (
    TabletLayoutFormatError,
    layout_from_dict,
    layout_to_dict,
)
from geoworkbench.tablet.models import (
    CurveDisplaySettings,
    CurveLineStyle,
    CurveStyle,
    TabletLayout,
    TrackDefinition,
    TrackKind,
    XScale,
)


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
    source.set_cursor_depth(1250.0)
    source.track_by_id("gas").set_curve_style("C1", CurveStyle("#ff0000", 2.5, CurveLineStyle.DASH))
    source.track_by_id("gas").set_curve_display(
        "C1",
        CurveDisplaySettings("Метан", XScale.LOGARITHMIC, 0.1, 100.0),
    )
    source.track_by_id("gas").set_grid(False, True, 0.45)
    source.track_by_id("gas").set_x_axis_label("Gas, %")

    restored = layout_from_dict(layout_to_dict(source))

    assert restored == source
    assert restored.tracks[0].kind is TrackKind.DEPTH
    assert restored.visible_depth_top == 1200.0
    assert restored.visible_depth_bottom == 1300.0
    assert restored.cursor_depth == 1250.0
    assert restored.track_by_id("gas").curve_style("C1") == CurveStyle(
        "#ff0000", 2.5, CurveLineStyle.DASH
    )
    assert restored.track_by_id("gas").curve_display_settings("C1") == CurveDisplaySettings(
        "Метан", XScale.LOGARITHMIC, 0.1, 100.0
    )
    assert restored.track_by_id("gas").grid_x is False
    assert restored.track_by_id("gas").grid_y is True
    assert restored.track_by_id("gas").grid_alpha == 0.45
    assert restored.track_by_id("gas").x_axis_label == "Gas, %"


def test_layout_codec_migrates_v3_without_curve_styles() -> None:
    restored = layout_from_dict(
        {
            "version": 3,
            "visible_depth_top": None,
            "visible_depth_bottom": None,
            "tracks": [
                {
                    "track_id": "curve",
                    "title": "Curve",
                    "kind": "curve",
                    "curve_mnemonics": ["GR"],
                }
            ],
        }
    )
    assert restored.track_by_id("curve").curve_styles == {}


def test_layout_codec_migrates_v4_with_default_grid() -> None:
    restored = layout_from_dict(
        {
            "version": 4,
            "tracks": [
                {
                    "track_id": "curve",
                    "title": "Curve",
                    "kind": "curve",
                    "curve_styles": {},
                }
            ],
        }
    )

    track = restored.track_by_id("curve")
    assert track.grid_x is True
    assert track.grid_y is True
    assert track.grid_alpha == 0.2


def test_layout_codec_migrates_v5_with_empty_axis_label() -> None:
    restored = layout_from_dict(
        {
            "version": 5,
            "tracks": [{"track_id": "curve", "title": "Curve", "kind": "curve"}],
        }
    )

    assert restored.track_by_id("curve").x_axis_label == ""


@pytest.mark.parametrize("alpha", [-0.01, 1.01, float("nan"), True])
def test_track_rejects_invalid_grid_alpha(alpha: object) -> None:
    with pytest.raises(ValueError, match="Прозрачность сетки"):
        TrackDefinition("curve", "Curve", TrackKind.CURVE, grid_alpha=alpha)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "style",
    [
        CurveStyle("#AABBCC", 0.5, CurveLineStyle.SOLID),
        CurveStyle("#000000", 10.0, CurveLineStyle.DASH_DOT),
    ],
)
def test_curve_style_accepts_supported_boundaries(style: CurveStyle) -> None:
    assert style.color.startswith("#")


def test_curve_style_rejects_invalid_color_and_width() -> None:
    with pytest.raises(ValueError, match="RRGGBB"):
        CurveStyle("red")
    with pytest.raises(ValueError, match="0.5"):
        CurveStyle("#ff0000", 0.1)


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


def test_layout_codec_round_trip_preserves_vertical_index() -> None:
    source = make_layout()
    source.vertical_index_id = "time-index"

    restored = layout_from_dict(layout_to_dict(source))

    assert restored.vertical_index_id == "time-index"


def test_layout_codec_migrates_v7_without_vertical_index() -> None:
    restored = layout_from_dict(
        {
            "version": 7,
            "visible_depth_top": None,
            "visible_depth_bottom": None,
            "cursor_depth": None,
            "tracks": [],
        }
    )

    assert restored.vertical_index_id is None


def test_switching_vertical_index_resets_incompatible_window_and_cursor() -> None:
    layout = make_layout()
    layout.set_visible_depth(1000.0, 1100.0)
    layout.set_cursor_depth(1050.0)

    assert layout.set_vertical_index("time-index") is True
    assert layout.visible_depth_top is None
    assert layout.visible_depth_bottom is None
    assert layout.cursor_depth is None


def test_curve_display_settings_validate_manual_range() -> None:
    with pytest.raises(ValueError):
        CurveDisplaySettings("Bad", XScale.LOGARITHMIC, 0.0, 10.0)


def test_layout_codec_migrates_v8_with_empty_curve_display() -> None:
    restored = layout_from_dict(
        {
            "version": 8,
            "vertical_index_id": None,
            "tracks": [
                {
                    "track_id": "curve",
                    "title": "Curve",
                    "kind": "curve",
                    "curve_mnemonics": ["GR"],
                }
            ],
        }
    )
    assert restored.track_by_id("curve").curve_display == {}
