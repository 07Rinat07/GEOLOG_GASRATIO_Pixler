"""Non-destructive report-preview overlay validation."""
import pytest

from geoworkbench.services.report_preview_marks import PreviewMark, PreviewMarkKind, PreviewOverlay


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


def test_overlay_edit_operations_preserve_previous_versions():
    a = PreviewMark(PreviewMarkKind.TEXT, 0, 0.1, 0.2, text="A")
    b = PreviewMark(PreviewMarkKind.COMMENT, 1, 0.3, 0.4, text="B")
    empty = PreviewOverlay()
    first = empty.add(a)
    second = first.add(b)
    edited = second.replace(0, b)
    removed = edited.remove(1)
    assert empty.marks == ()
    assert first.marks == (a,)
    assert second.marks == (a, b)
    assert edited.marks == (b, b)
    assert removed.marks == (b,)


def test_overlay_rejects_invalid_edits_without_mutation():
    a = PreviewMark(PreviewMarkKind.TEXT, 0, 0, 0, text="A")
    overlay = PreviewOverlay((a,))
    for invalid_index in (-1, 1, True, 0.5):
        with pytest.raises(IndexError):
            overlay.remove(invalid_index)
        with pytest.raises(IndexError):
            overlay.replace(invalid_index, a)
    with pytest.raises(ValueError):
        overlay.add(None)
    with pytest.raises(ValueError):
        overlay.replace(0, None)
    with pytest.raises(ValueError):
        PreviewOverlay((None,))
    assert overlay.marks == (a,)
