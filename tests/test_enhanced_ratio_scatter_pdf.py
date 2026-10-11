"""Enhanced Wh/Bh/Ch PDF ratio tracks must remain factual scatter observations."""

from __future__ import annotations

from unittest.mock import MagicMock

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPdfWriter, QPen

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage
from geoworkbench.services.gas_curve_presentation import gas_scatter_point_budget
from geoworkbench.services.localization import AppLanguage


def _ratios(rows: int = 101):
    depth = np.linspace(100.0, 110.0, rows)
    dataset = Dataset("ratio-scatter", "Ratios", DatasetKind.GTI, DepthDomain.MD, depth)
    values = (
        np.linspace(1.0, 3.0, rows),
        np.linspace(4.0, 1.0, rows),
        np.linspace(1.0, 4.0, rows),
    )
    curves = tuple(
        dataset.upsert_curve(name, current)
        for name, current in zip(("WH", "BH", "CH"), values, strict=True)
    )
    return dataset, curves


def _mock_headers(monkeypatch) -> None:
    monkeypatch.setattr(enhanced, "paint_track_heading", lambda *a, **k: None)
    monkeypatch.setattr(enhanced, "paint_ratio_scale_heading", lambda *a, **k: None)
    monkeypatch.setattr(enhanced, "ratio_scale_header_height", lambda *a, **k: 10.0)


@pytest.mark.parametrize("rows", (11, 10001))
def test_enhanced_pdf_ratio_tracks_use_only_bounded_scatter_marks(
    qapp, monkeypatch, rows,
):
    _mock_headers(monkeypatch)
    dataset, curves = _ratios(rows)
    before_depth = dataset.depth.copy()
    before_curves = [curve.values.copy() for curve in curves]
    painter = MagicMock()
    rect = QRectF(20.0, 30.0, 220.0, 300.0)
    page = DepthPage(100.0, 110.0, 100, 300.0)
    assert enhanced._draw_ratio_tracks(
        painter, rect, page, dataset, curves, (), AppLanguage.EN, header_height=40.0,
    )
    assert painter.drawEllipse.call_count > 0
    assert painter.drawEllipse.call_count <= 3 * gas_scatter_point_budget(rect.height())
    painter.drawPolyline.assert_not_called()
    # Legacy printer contract still requires a colored dashed 0.7-pt outline.
    ratio_outlines = [
        call.args[0] for call in painter.setPen.call_args_list
        if call.args and isinstance(call.args[0], QPen)
        and call.args[0].style() == Qt.PenStyle.DashLine
    ]
    assert len(ratio_outlines) >= 3
    assert all(pen.widthF() == pytest.approx(0.7) for pen in ratio_outlines)
    for call in painter.drawEllipse.call_args_list:
        center, radius_x, radius_y = call.args
        assert 20.0 <= center.x() <= 240.0
        assert 30.0 <= center.y() <= 330.0
        assert radius_x > 0 and radius_y > 0
    np.testing.assert_array_equal(dataset.depth, before_depth)
    for curve, original in zip(curves, before_curves, strict=True):
        np.testing.assert_array_equal(curve.values, original)


def test_enhanced_pdf_ratio_log_tracks_reject_nonpositive_points(qapp, monkeypatch):
    _mock_headers(monkeypatch)
    dataset, curves = _ratios(5)
    curves[0].values[:] = [-2.0, 0.0, 2.0, np.nan, 3.0]
    source = curves[0].values.copy()
    painter = MagicMock()
    assert enhanced._draw_ratio_tracks(
        painter, QRectF(0, 10, 100, 200),
        DepthPage(100.0, 110.0, 100, 200.0),
        dataset, (curves[0],), (), AppLanguage.EN, header_height=40.0,
    )
    assert painter.drawEllipse.call_count == 2
    painter.drawPolyline.assert_not_called()
    np.testing.assert_array_equal(curves[0].values, source)


def test_enhanced_ratio_pdf_uses_vector_point_geometry(qapp, tmp_path, monkeypatch):
    _mock_headers(monkeypatch)
    dataset, curves = _ratios(11)
    path = tmp_path / "haworth-scatter.pdf"
    writer = QPdfWriter(str(path))
    writer.setResolution(72)
    painter = QPainter(writer)
    try:
        assert enhanced._draw_ratio_tracks(
            painter, QRectF(20, 60, 230, 260),
            DepthPage(100.0, 110.0, 100, 260.0),
            dataset, curves, (), AppLanguage.EN, header_height=40.0,
        )
    finally:
        painter.end()
    with fitz.open(path) as document:
        drawings = document[0].get_drawings()
        assert any(
            item[0] == "c" for drawing in drawings for item in drawing["items"]
        ), "Expected vector ellipse outlines for individual ratio observations"
