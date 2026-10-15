"""Non-destructive report-preview overlay validation."""
import pytest

from geoworkbench.services.report_preview_marks import (
    PreviewMark, PreviewMarkKind, PreviewOverlay, PreviewEditHistory,
    find_preview_mark, translate_preview_mark,
)


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


def test_preview_history_undo_redo_and_divergent_edit():
    a = PreviewMark(PreviewMarkKind.TEXT, 0, 0, 0, text="A")
    b = PreviewMark(PreviewMarkKind.TEXT, 0, 1, 1, text="B")
    original = PreviewEditHistory()
    one = original.apply(original.current.add(a))
    two = one.apply(one.current.add(b))
    undone = two.undo()
    assert undone.current.marks == (a,)
    assert undone.redo().current.marks == (a, b)
    divergent = undone.apply(undone.current.remove(0))
    assert divergent.current.marks == ()
    assert divergent.redo_stack == ()
    assert divergent.undo().current.marks == (a,)
    assert original.current.marks == ()


def test_preview_history_noop_and_bounded_snapshots():
    history = PreviewEditHistory()
    assert history.undo() is history
    assert history.redo() is history
    assert history.apply(history.current) is history
    for i in range(110):
        mark = PreviewMark(PreviewMarkKind.TEXT, 0, 0, 0, text=str(i))
        history = history.apply(history.current.add(mark))
    assert len(history.undo_stack) == 100
    assert history.current.marks[-1].text == "109"
    with pytest.raises(ValueError):
        history.apply(None)
    with pytest.raises(ValueError):
        PreviewEditHistory(undo_stack=(PreviewOverlay(),) * 101)


def test_hit_testing_respects_page_stacking_and_stroke_segments():
    background = PreviewMark(PreviewMarkKind.TEXT, 0, 0.3, 0.3, text="Behind")
    foreground = PreviewMark(PreviewMarkKind.COMMENT, 0, 0.3, 0.3, text="Above")
    stroke = PreviewMark(
        PreviewMarkKind.FREEHAND, 1, 0.1, 0.1,
        points=((0.1, 0.1), (0.7, 0.7)),
    )
    marks = (background, foreground, stroke)
    assert find_preview_mark(marks, 0, 0.3, 0.3) == 1
    assert find_preview_mark(marks, 1, 0.4, 0.4) == 2
    assert find_preview_mark(marks, 0, 0.4, 0.4) is None
    assert find_preview_mark(marks, 1, 0.5, 0.2) is None
    assert find_preview_mark(marks, 2, 0.3, 0.3) is None


def test_stroke_translation_preserves_shape_and_clamps_without_crossing_page():
    stroke = PreviewMark(
        PreviewMarkKind.FREEHAND, 2, 0.15, 0.2,
        points=((0.15, 0.2), (0.35, 0.4), (0.7, 0.8)),
    )
    translated = translate_preview_mark(stroke, 0.1, -0.1)
    assert translated.page == 2
    for (x, y), (expected_x, expected_y) in zip(translated.points, ((0.25, 0.1), (0.45, 0.3), (0.8, 0.7)), strict=True):
        assert x == pytest.approx(expected_x)
        assert y == pytest.approx(expected_y)
    assert stroke.points[0] == (0.15, 0.2)
    bounded = translate_preview_mark(stroke, 5.0, -5.0)
    assert min(y for _, y in bounded.points) == pytest.approx(0.0)
    assert max(x for x, _ in bounded.points) == pytest.approx(1.0)
    assert bounded.points[2][0] - bounded.points[0][0] == pytest.approx(0.55)
    assert bounded.points[2][1] - bounded.points[0][1] == pytest.approx(0.6)


@pytest.mark.parametrize("dx,dy", [
    (float("nan"), 0), (0, float("inf")), (True, 0), ("bad", 0),
])
def test_stroke_translation_rejects_invalid_delta(dx, dy):
    mark = PreviewMark(PreviewMarkKind.TEXT, 0, 0.5, 0.5, text="x")
    with pytest.raises(ValueError):
        translate_preview_mark(mark, dx, dy)
