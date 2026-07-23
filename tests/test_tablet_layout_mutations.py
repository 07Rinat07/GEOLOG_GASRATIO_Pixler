from __future__ import annotations

from geoworkbench.tablet.layout_mutations import TabletLayoutMutationController
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind


def test_layout_mutation_controller_owns_width_order_and_view_state_changes() -> None:
    layout = TabletLayout(
        [
            TrackDefinition("a", "A", TrackKind.CURVE, width=200),
            TrackDefinition("b", "B", TrackKind.CURVE, width=220),
        ]
    )
    controller = TabletLayoutMutationController(layout)

    assert controller.set_track_width("a", 320) is True
    assert controller.set_track_width("a", 320) is False
    assert controller.move_track_to_index("a", 1) is True
    assert controller.move_track_to_index("a", 1) is False
    assert controller.set_vertical_index("depth-index") is True
    assert controller.set_visible_depth(100.0, 200.0) is True

    assert [track.track_id for track in layout.tracks] == ["b", "a"]
    assert layout.track_by_id("a").width == 320
    assert (layout.visible_depth_top, layout.visible_depth_bottom) == (100.0, 200.0)
    assert layout.vertical_index_id == "depth-index"


def test_layout_mutation_controller_rebinds_without_mutating_previous_layout() -> None:
    first = TabletLayout([TrackDefinition("a", "A", TrackKind.CURVE)])
    second = TabletLayout([TrackDefinition("b", "B", TrackKind.CURVE)])
    controller = TabletLayoutMutationController(first)

    controller.bind(second)
    controller.set_track_width("b", 410)

    assert first.track_by_id("a").width != 410
    assert second.track_by_id("b").width == 410
