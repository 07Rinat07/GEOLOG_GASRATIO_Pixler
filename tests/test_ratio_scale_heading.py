from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing import ratio_scale_heading as heading
from geoworkbench.services.gas_curve_presentation import GasRatioScale, gas_ratio_scale_ticks
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing.gas_ratio_reference import ratio_reference_color
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.services.localization import AppLanguage
from test_interpretation_chart_readability import _dataset, _report
from test_interpretation_text_physical_dpi import _spans


@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('width', [22.0, 40.0, 90.0])
@pytest.mark.parametrize('scale', [GasRatioScale(0.1, 100.0, True), GasRatioScale(0.0, 5.0),
                                 GasRatioScale(1.0, 1000.0, True)])
def test_readable_scale_endpoints_are_complete_bounded_and_do_not_overlap(
    qapp: object, tmp_path: Path, dpi: int, width: float, scale: GasRatioScale,
) -> None:
    output = tmp_path / 'scale.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        heading.paint_ratio_scale_heading(painter, QRectF(50, 120, width, 300),
                                         'Wh / Bh', gas_ratio_scale_ticks(scale))
    finally:
        painter.end()
    with fitz.open(output) as document:
        spans = [span for span in _spans(document[0]) if span['text'][0].isdigit()]
        endpoints = [label for _, label in (gas_ratio_scale_ticks(scale)[0], gas_ratio_scale_ticks(scale)[-1])]
        assert all(any(span['text'] == label for span in spans) for label in endpoints)
        assert all(span['size'] == pytest.approx(7.0, abs=0.08) for span in spans)
        assert all(49.5 <= span['bbox'][0] < span['bbox'][2] <= 50 + width + 0.5 for span in spans)
        assert all(span['bbox'][3] < 120 for span in spans)
        for index, span in enumerate(spans):
            for other in spans[index+1:]:
                assert not fitz.Rect(span['bbox']).intersects(fitz.Rect(other['bbox']))
        if width == 90:
            assert len(spans) == 3


@pytest.mark.parametrize('dpi', [72, 300, 600])
def test_scale_caption_profile_controls_actual_pdf_font_and_reserved_height(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dpi: int,
) -> None:
    profile = heading.modern_oilfield_report_profile()
    profile = replace(profile, typography=replace(profile.typography, caption_pt=9.0))
    monkeypatch.setattr(heading, 'modern_oilfield_report_profile', lambda: profile)
    output = tmp_path / 'profile.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        reserved = heading.ratio_scale_header_height(writer)
        heading.paint_ratio_scale_heading(painter, QRectF(50, 120, 120, 300),
                                         'C1/C2', gas_ratio_scale_ticks(GasRatioScale(1, 1000, True)))
    finally:
        painter.end()
    with fitz.open(output) as document:
        spans = _spans(document[0])
        assert len(spans) == 4
        assert all(span['size'] == pytest.approx(9.0, abs=0.08) for span in spans)
        assert all(span['bbox'][1] >= 120 - reserved - 0.5 and span['bbox'][3] < 120 for span in spans)


@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('landscape', [False, True])
def test_production_ratio_heading_is_readable_once_per_lane_and_above_traces(
    qapp: object, tmp_path: Path, dpi: int, language: AppLanguage, landscape: bool,
) -> None:
    dataset = _dataset()
    before = deepcopy(dataset)
    output = tmp_path / 'chart.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape
                              else QPageLayout.Orientation.Portrait)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        enhanced.render_chart_pages(PageCanvas(writer, painter, language), _report('opus'), dataset, language)
    finally:
        painter.end()
    with fitz.open(output) as document:
        for page in document:
            spans = _spans(page)
            identifiers = [span for span in spans if span['text'] == 'Wh / Bh']
            assert len(identifiers) == 1
            assert identifiers[0]['size'] == pytest.approx(7.0, abs=0.08)
            reference = ratio_reference_color(dataset.curves['WH']).getRgbF()[:3]
            traces = [draw for draw in page.get_drawings() if draw['color'] and
                      all(abs(a-b) < 0.002 for a,b in zip(draw['color'], reference, strict=True))]
            assert traces
            trace_top = min(draw['rect'].y0 for draw in traces)
            labels = [span for span in spans if span['text'] in ('0.1', '100') and
                      identifiers[0]['bbox'][3] < span['bbox'][1] < trace_top]
            assert {span['text'] for span in labels} == {'0.1', '100'}
            assert all(span['size'] == pytest.approx(7.0, abs=0.08) and span['bbox'][3] < trace_top
                       for span in labels)
    assert np.array_equal(dataset.depth, before.depth)
    for key, curve in dataset.curves.items():
        assert np.array_equal(curve.values, before.curves[key].values)
        assert curve.metadata == before.curves[key].metadata
