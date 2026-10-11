"""Production-painter regression for monochrome interpretation curve identity."""

from __future__ import annotations

from unittest.mock import MagicMock

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPdfWriter, QPen

from geoworkbench.domain.models import (
    CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain,
)
from geoworkbench.printing import hydrocarbon_interpretation_chart as preview
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as pdf
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage
from geoworkbench.printing.interpretation_curve_strokes import curve_line_pen_style
from geoworkbench.services.localization import AppLanguage


def _source_curves() -> tuple[Dataset, tuple[CurveData, ...]]:
    depth = np.array([100.0, 101.0, 102.0, 103.0])
    dataset = Dataset("stroke-dataset", "GTI", DatasetKind.GTI, DepthDomain.MD, depth)
    curves = tuple(
        CurveData(
            CurveMetadata(
                f"curve-{index}", name, name, "m/h", "Curve", dataset.dataset_id,
            ),
            np.array([float(index + 1), float(index + 2),
                      float(index + 3), float(index + 4)]),
        )
        for index, name in enumerate(("ROP", "WOB", "FLOW_IN"))
    )
    for curve in curves:
        dataset.curves[curve.metadata.curve_id] = curve
    return dataset, curves


@pytest.mark.parametrize("index", range(12))
def test_strokes_repeat_deterministically_for_curve_and_legend(index: int) -> None:
    patterns = (
        Qt.PenStyle.SolidLine, Qt.PenStyle.DashLine, Qt.PenStyle.DotLine,
        Qt.PenStyle.DashDotLine, Qt.PenStyle.DashDotDotLine,
    )
    assert curve_line_pen_style(index) == patterns[index % len(patterns)]


@pytest.mark.parametrize("invalid", (-1, True, 1.5, "1", None))
def test_stroke_index_rejects_invalid_input(invalid: object) -> None:
    with pytest.raises(ValueError, match="curve_index"):
        curve_line_pen_style(invalid)


def test_standard_pdf_curves_have_distinct_strokes_without_changing_sources(qapp) -> None:
    dataset, curves = _source_curves()
    depth_before = dataset.depth.copy()
    source_before = [curve.values.copy() for curve in curves]
    ranges = {
        curve.metadata.curve_id: (float(curve.values.min()), float(curve.values.max()))
        for curve in curves
    }
    painter = MagicMock()
    pdf._draw_curves(
        painter, QRectF(20, 40, 220, 260),
        DepthPage(100.0, 103.0, 100, 100.0),
        dataset, curves, ranges, point_series=False,
    )
    strokes = [
        call.args[0].style()
        for call in painter.setPen.call_args_list
        if call.args and isinstance(call.args[0], QPen)
    ]
    assert strokes == [curve_line_pen_style(i) for i in range(3)]
    assert painter.drawLine.call_count > 0
    np.testing.assert_array_equal(dataset.depth, depth_before)
    for curve, old in zip(curves, source_before, strict=True):
        np.testing.assert_array_equal(curve.values, old)


def test_preview_curve_and_legend_have_the_same_noncolor_strokes(qapp, monkeypatch) -> None:
    dataset, curves = _source_curves()
    monkeypatch.setattr(preview, "_paint_preview_text", lambda *args, **kwargs: None)
    painter = MagicMock()
    painter.device.return_value.logicalDpiY.return_value = 96
    preview._draw_panel(
        painter, QRectF(20, 70, 300, 300),
        dataset.depth, np.isfinite(dataset.depth), 100.0, 103.0,
        "total", curves, (), AppLanguage.EN, {},
    )
    for i in range(3):
        color = QColor(preview._COLORS[i])
        matching = [
            call.args[0]
            for call in painter.setPen.call_args_list
            if call.args and isinstance(call.args[0], QPen)
            and call.args[0].color() == color
        ]
        assert len(matching) >= 2
        assert {pen.style() for pen in matching} == {curve_line_pen_style(i)}
    assert painter.drawLine.call_count > 0


def test_vector_pdf_contains_dashed_curves_and_matching_legend(qapp, tmp_path) -> None:
    dataset, curves = _source_curves()
    path = tmp_path / "monochrome-curves.pdf"
    writer = QPdfWriter(str(path))
    writer.setResolution(72)
    painter = QPainter(writer)
    try:
        ranges = {
            curve.metadata.curve_id: (float(curve.values.min()), float(curve.values.max()))
            for curve in curves
        }
        pdf._draw_curves(
            painter, QRectF(25, 60, 220, 240),
            DepthPage(100.0, 103.0, 100, 100.0),
            dataset, curves, ranges, point_series=False,
        )
        pdf._draw_legend(
            painter, QRectF(25, 330, 460, 180), 0, 1,
            curves, ranges, language=AppLanguage.EN, point_series=False,
        )
    finally:
        painter.end()
    with fitz.open(path) as document:
        drawings = document[0].get_drawings()
        assert any(
            drawing.get("dashes") not in (None, "[] 0")
            for drawing in drawings
        ), "Curves must remain distinguishable by dashed geometry in PDF"
        text = document[0].get_text()
        assert "Rate of Penetration [m/h]" in text
        assert "Weight on Bit [m/h]" in text
        assert "Flow In [m/h]" in text
