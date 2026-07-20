from geoworkbench.printing.form_column_layout import (
    adaptive_column_layout,
    original_column_layout,
)
from geoworkbench.tablet.models import TrackDefinition, TrackKind


def _tracks() -> list[TrackDefinition]:
    return [
        TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
        TrackDefinition("gas", "Gas", TrackKind.GAS, width=420),
        TrackDefinition("rop", "ROP", TrackKind.CURVE, width=360),
        TrackDefinition("lith", "Lithology", TrackKind.LITHOLOGY, width=220),
        TrackDefinition("text", "Text", TrackKind.TEXT, width=520),
    ]


def test_adaptive_columns_keep_every_track_and_readable_minimums() -> None:
    layout = adaptive_column_layout(
        _tracks(),
        page_aspect_ratio=210 / 297,
        content_height=700,
    )

    assert len(layout.widths) == 5
    assert layout.widths[0] >= 96
    assert all(width >= 80 for width in layout.widths)
    assert layout.total_width >= sum(layout.widths)


def test_landscape_allocates_more_horizontal_space_than_portrait() -> None:
    portrait = adaptive_column_layout(
        _tracks(),
        page_aspect_ratio=210 / 297,
        content_height=700,
    )
    landscape = adaptive_column_layout(
        _tracks(),
        page_aspect_ratio=297 / 210,
        content_height=700,
    )

    assert landscape.total_width > portrait.total_width
    assert sum(landscape.widths) > sum(portrait.widths)


def test_extreme_screen_width_is_capped_before_print_distribution() -> None:
    tracks = [
        TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
        TrackDefinition("wide", "Wide", TrackKind.CURVE, width=2000),
        TrackDefinition("normal", "Normal", TrackKind.CURVE, width=260),
    ]
    layout = adaptive_column_layout(
        tracks,
        page_aspect_ratio=297 / 210,
        content_height=700,
    )

    assert layout.widths[1] < layout.widths[2] * 2


def test_original_layout_preserves_form_widths() -> None:
    layout = original_column_layout(_tracks())

    assert layout.widths == (120, 420, 360, 220, 520)
