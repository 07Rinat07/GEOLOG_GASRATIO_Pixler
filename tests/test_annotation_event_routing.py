from geoworkbench.project.annotation_schema import (
    AnnotationAnchor,
    AnnotationKind,
    AnnotationRecord,
)
from geoworkbench.tablet.annotation_graphics import TabletAnnotationItem
from geoworkbench.tablet.tablet_view import TabletView


def _record() -> AnnotationRecord:
    return AnnotationRecord(
        annotation_id="annotation-1",
        kind=AnnotationKind.CALLOUT,
        anchor=AnnotationAnchor.DEPTH,
        text="Рейс",
        track_id="track-1",
        depth=100.0,
        axis_value=100.0,
        axis_id="depth",
        parameter_mnemonic=None,
        parameter_value=None,
        unit="",
        x_fraction=0.5,
        offset_x=18.0,
        offset_y=-36.0,
        width=220.0,
        height=76.0,
    )


def test_annotation_scene_hit_is_not_treated_as_curve_hit(qapp) -> None:
    item = TabletAnnotationItem(_record(), edit_mode=True)

    assert TabletView._annotation_ancestor(item) is item
    assert item.acceptedMouseButtons()
    assert item.flags() & item.GraphicsItemFlag.ItemIsFocusable
    assert item.flags() & item.GraphicsItemFlag.ItemIsSelectable
