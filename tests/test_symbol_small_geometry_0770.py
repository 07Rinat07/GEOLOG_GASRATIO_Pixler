from geoworkbench.domain.models import CanvasObject
from geoworkbench.project.annotation_schema import (
    ANNOTATION_OBJECT_TYPE,
    AnnotationKind,
    annotation_from_canvas,
)


def test_small_catalog_symbol_geometry_survives_project_decode() -> None:
    item = CanvasObject(
        object_id="symbol-small",
        object_type=ANNOTATION_OBJECT_TYPE,
        anchor_type="depth",
        x=0.5,
        y=100.0,
        width=2.0,
        height=3.0,
        top_depth=100.0,
        bottom_depth=100.0,
        track_id="gas",
        properties={
            "kind": AnnotationKind.SYMBOL.value,
            "symbol_id": "symbol-bit",
            "asset_ref": "asset-symbol-bit",
        },
    )

    record = annotation_from_canvas(item)

    assert record.kind is AnnotationKind.SYMBOL
    assert record.width == 2.0
    assert record.height == 3.0


def test_non_symbol_annotation_keeps_safe_minimum_geometry() -> None:
    item = CanvasObject(
        object_id="comment-small",
        object_type=ANNOTATION_OBJECT_TYPE,
        anchor_type="depth",
        x=0.5,
        y=100.0,
        width=2.0,
        height=3.0,
        top_depth=100.0,
        bottom_depth=100.0,
        track_id="gas",
        properties={"kind": AnnotationKind.COMMENT.value},
    )

    record = annotation_from_canvas(item)

    assert record.width == 40.0
    assert record.height == 24.0
