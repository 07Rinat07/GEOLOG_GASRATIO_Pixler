"""Ratio/Pixler label rectangles and their physical PDF glyphs must not overlap."""

from __future__ import annotations

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF

from geoworkbench.printing import gas_ratio_reference as reference
from geoworkbench.services.localization import AppLanguage
from test_gas_ratio_reference import _dataset
from test_ratio_reference_physical_dpi import _export


def _disjoint(a: QRectF, b: QRectF) -> bool:
    return not a.intersects(b)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_ratio_labels_use_disjoint_reserved_rectangles(qapp, monkeypatch, language):
    dataset = _dataset()
    before = {name: curve.values.copy() for name, curve in dataset.curves.items()}
    captured: list[tuple[str, QRectF]] = []
    original = reference._text

    def capture(painter, rect, label, size=None, **kwargs):
        captured.append((label, QRectF(rect)))
        original(painter, rect, label, size, **kwargs)

    monkeypatch.setattr(reference, "_text", capture)
    assert reference.ratio_reference_summary_uri(dataset, language)
    axes = [rect for label, rect in captured if label in ("Balance (Bh)", "Character (Ch)")]
    depths = [rect for label, rect in captured if "–" in label and label.endswith(" m")]
    heading = next(rect for label, rect in captured if label.startswith("Pixler ·"))
    zeros_x = [rect for label, rect in captured if label == "0"]
    zeros_y = [rect for label, rect in captured if label == "0.0"]
    assert len(axes) == len(zeros_x) == len(zeros_y) == 2
    assert len(depths) == 6
    for axis in axes:
        assert all(_disjoint(axis, legend) for legend in depths)
    for legend in depths:
        assert _disjoint(legend, heading)
    for xrect, yrect in zip(zeros_x, zeros_y, strict=True):
        assert _disjoint(xrect, yrect)
    # Pixler's leftmost X category must not sit on the lowest logarithmic Y label.
    category = next(rect for label, rect in captured if label == "C1/C2")
    lowest_log = next(
        rect for label, rect in captured
        if label == "1" and rect.left() == 12.0 and rect.top() >= 575.0
    )
    assert lowest_log.center().y() == pytest.approx(680.0)
    assert category.center().x() == pytest.approx(65.0)
    assert [rect.center().x() for rect in zeros_x] == pytest.approx([65.0, 555.0])
    assert _disjoint(category, lowest_log)
    for name, curve in dataset.curves.items():
        np.testing.assert_array_equal(curve.values, before[name])


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", (72, 300))
def test_ratio_pdf_real_text_spans_have_no_axis_key_overlap(qapp, tmp_path, language, dpi):
    destination = tmp_path / f"ratios-{dpi}.pdf"
    _export(destination, _dataset(), language, dpi, False)
    with fitz.open(destination) as document:
        spans = [
            span
            for block in document[0].get_text("dict")["blocks"]
            if "lines" in block
            for line in block["lines"]
            for span in line["spans"]
        ]
    def box(span):
        return fitz.Rect(span["bbox"])
    axis_names = [box(s) for s in spans if s["text"] in ("Balance (Bh)", "Character (Ch)")]
    depth_names = [box(s) for s in spans if "–" in s["text"] and s["text"].endswith(" m")]
    pixler = next(box(s) for s in spans if s["text"].startswith("Pixler ·"))
    xzero = [box(s) for s in spans if s["text"] == "0"]
    yzero = [box(s) for s in spans if s["text"] == "0.0"]
    assert len(axis_names) == len(xzero) == len(yzero) == 2
    assert len(depth_names) == 6
    for label in axis_names:
        assert all((label & depth).is_empty for depth in depth_names)
    assert all((pixler & depth).is_empty for depth in depth_names)
    for x, y in zip(xzero, yzero, strict=True):
        assert (x & y).is_empty


@pytest.mark.parametrize("minimum,maximum,height", (
    (0.0, 3.0, 205.0),
    (0.0, 9.0, 205.0),
    (-4.0, 5.0, 205.0),
    (0.0, 10.0, 205.0),
    (-4.0, 12.0, 205.0),
    (-80.0, 120.0, 205.0),
    (0.0, 20.0, 50.0),
))
def test_pixler_log_tick_labels_are_bounded_and_spaced(minimum, maximum, height):
    powers = reference._pixler_log_tick_powers(minimum, maximum, height)
    assert powers[0] == int(minimum)
    assert powers[-1] == int(maximum)
    assert len(powers) <= max(2, int(height // 32) + 1)
    if len(powers) > 1:
        y_positions = [height * (value - minimum) / (maximum - minimum) for value in powers]
        assert min(b - a for a, b in zip(y_positions, y_positions[1:])) >= 24.0


@pytest.mark.parametrize("height", (50.0, 100.0, 205.0, 500.0))
@pytest.mark.parametrize("decades", range(1, 31))
def test_log_tick_spacing_survives_integer_decade_selection(
    height: float, decades: int,
) -> None:
    powers = reference._pixler_log_tick_powers(-3.0, float(decades - 3), height)
    assert powers[0] == -3 and powers[-1] == decades - 3
    assert tuple(sorted(set(powers))) == powers
    assert len(powers) <= max(2, int(height // 32.0) + 1)
    pixel_positions = [height * (power + 3) / decades for power in powers]
    assert all(
        next_position - position >= 24.0 - 1e-9
        for position, next_position in zip(pixel_positions, pixel_positions[1:])
    )
