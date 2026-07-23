from __future__ import annotations

import pytest

from geoworkbench.project.annotation_schema import (
    AnnotationAnchor,
    AnnotationKind,
    AnnotationRecord,
    AnnotationStyle,
)
from geoworkbench.tablet.annotation_layout import LayoutPoint, LayoutRect, layout_annotation


def test_annotation_layout_scales_reference_pixels_to_print_units() -> None:
    record = _record()
    screen = layout_annotation(record, anchor_x=100.0, anchor_y=200.0)
    printed = layout_annotation(
        record,
        anchor_x=10.0,
        anchor_y=20.0,
        pixel_scale=25.4 / 96.0,
    )

    assert printed.box.width == pytest.approx(screen.box.width * 25.4 / 96.0)
    assert printed.box.height == pytest.approx(screen.box.height * 25.4 / 96.0)
    assert screen.leader_endpoint == LayoutPoint(118.0, 200.0)


def test_annotation_layout_clamps_box_but_keeps_leader_at_shared_geometry() -> None:
    record = _record(offset_x=50.0, offset_y=50.0, width=180.0, height=60.0)
    layout = layout_annotation(
        record,
        anchor_x=95.0,
        anchor_y=95.0,
        bounds=LayoutRect(0.0, 0.0, 100.0, 100.0),
        visible_margin=10.0,
        max_width=100.0,
        max_height=100.0,
    )

    assert layout.box.left == 90.0
    assert layout.box.top == 90.0
    assert layout.leader_endpoint is not None


def _record(
    *,
    offset_x: float = 18.0,
    offset_y: float = -46.0,
    width: float = 220.0,
    height: float = 76.0,
) -> AnnotationRecord:
    return AnnotationRecord(
        annotation_id="golden",
        kind=AnnotationKind.CALLOUT,
        anchor=AnnotationAnchor.DEPTH,
        text="Test",
        track_id="gas",
        depth=1000.0,
        axis_value=None,
        axis_id=None,
        parameter_mnemonic=None,
        parameter_value=None,
        unit="",
        x_fraction=0.5,
        offset_x=offset_x,
        offset_y=offset_y,
        width=width,
        height=height,
        style=AnnotationStyle(),
        asset_ref=None,
        visible=True,
        locked=False,
        print_enabled=True,
        scope_id=None,
    )
