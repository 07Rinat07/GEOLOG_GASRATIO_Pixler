"""Non-destructive report-preview overlay validation."""
import pytest

from geoworkbench.services.report_preview_marks import PreviewMark, PreviewMarkKind


def test_text_comment_and_symbol_marks_are_immutable():
    for kind in (PreviewMarkKind.TEXT, PreviewMarkKind.COMMENT, PreviewMarkKind.SYMBOL):
        mark = PreviewMark(kind, page=0, x=0.25, y=1.0, text="Geology")
        assert mark.text == "Geology"
        with pytest.raises(AttributeError):
            mark.text = "changed"


def test_freehand_stroke_is_bounded_and_normalized():
    mark = PreviewMark(
        PreviewMarkKind.FREEHAND, 1, 0, 0,
        points=((0, 0), (0.5, 0.75), (1, 1)),
    )
    assert mark.points[-1] == (1.0, 1.0)


@pytest.mark.parametrize("page,x,y", [
    (-1, 0, 0), (True, 0, 0), (0, -0.1, 0), (0, 0, 1.1),
    (0, float("nan"), 0), (0, 0, float("inf")), (0, True, 0),
])
def test_invalid_coordinates_and_page_rejected(page, x, y):
    with pytest.raises(ValueError):
        PreviewMark(PreviewMarkKind.TEXT, page, x, y, text="x")


def test_invalid_stroke_and_text_rejected():
    invalid = [
        dict(kind=PreviewMarkKind.TEXT, text=""),
        dict(kind=PreviewMarkKind.TEXT, text="x" * 4001),
        dict(kind=PreviewMarkKind.TEXT, text="x", points=((0, 0), (1, 1))),
        dict(kind=PreviewMarkKind.FREEHAND, points=((0, 0),)),
        dict(kind=PreviewMarkKind.FREEHAND, text="x", points=((0, 0), (1, 1))),
        dict(kind=PreviewMarkKind.FREEHAND, points=((0, 0), (float("nan"), 1))),
        dict(kind=PreviewMarkKind.FREEHAND, points=((0, 0),) * 4097),
    ]
    for values in invalid:
        with pytest.raises(ValueError):
            PreviewMark(page=0, x=0, y=0, **values)
