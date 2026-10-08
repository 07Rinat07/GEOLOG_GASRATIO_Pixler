from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any
import unicodedata

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing import curve_legend_layout as layout_module
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as standard
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing.curve_legend_layout import curve_legend_layout
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_interpretation_chart_readability import _dataset, _report


def _normalized(text: str) -> str:
    return ''.join(unicodedata.normalize('NFKC', text).split())


def _spans(page: fitz.Page) -> list[dict[str, Any]]:
    return [span for block in page.get_text('dict')['blocks'] if 'lines' in block
            for line in block['lines'] for span in line['spans']]


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('width', [100.0, 180.0, 300.0])
@pytest.mark.parametrize('caption', [7.2, 9.0])
def test_full_wrapped_legend_text_units_ranges_and_glyphs_fit_real_pdf(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    language: AppLanguage, dpi: int, width: float, caption: float,
) -> None:
    profile = modern_oilfield_report_profile()
    profile = replace(profile, typography=replace(profile.typography, caption_pt=caption))
    for module in (standard, layout_module):
        monkeypatch.setattr(module, 'modern_oilfield_report_profile', lambda: profile)
    dataset = _dataset()
    curves = tuple(dataset.curves[name] for name in ('TG_NORM_CALC', 'WH', 'BH', 'CH', 'C1_C2'))
    ranges = {curve.metadata.curve_id: (-1.234e-120, 9.876e120) for curve in curves}
    output = tmp_path / 'legend.pdf'
    writer = QPdfWriter(str(output))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    writer.setResolution(dpi)
    layout = curve_legend_layout(width, curves, ranges, language, writer)
    assert layout.height > 5 * 14.5
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        standard._draw_legend(painter, QRectF(30, 30, width, layout.height), 0, 1,
                              curves, ranges, language=language, point_series=False)
    finally:
        painter.end()
    with fitz.open(output) as document:
        page = document[0]
        spans = _spans(page)
        assert spans
        for row in layout.rows:
            assert _normalized(row.text) in _normalized(page.get_text())
        for span in spans:
            assert span['size'] == pytest.approx(round(caption), abs=0.08)
            bounds = fitz.Rect(span['bbox'])
            assert bounds.x0 >= 50.5
            assert bounds.x1 <= 30 + width + 0.5
            assert bounds.y0 >= 29.5
            assert bounds.y1 <= 30 + layout.height + 0.5
        for index, first in enumerate(spans):
            for second in spans[index + 1:]:
                intersection = fitz.Rect(first['bbox']) & fitz.Rect(second['bbox'])
                assert intersection.is_empty or intersection.width < 0.1 or intersection.height < 0.1
        drawings = page.get_drawings()
        for row in layout.rows:
            color = tuple(int(standard._COLORS[row.curve_index][i:i + 2], 16) / 255 for i in (1, 3, 5))
            samples = [draw for draw in drawings if draw['color'] and all(abs(a - b) < 0.002
                       for a, b in zip(draw['color'], color, strict=True))]
            assert len(samples) == 1
            assert samples[0]['rect'].y0 >= 30 + row.top
            assert samples[0]['rect'].y1 < 30 + row.top + row.line_height


@pytest.mark.parametrize('renderer', [standard, enhanced])
@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('landscape', [False, True])
def test_production_pages_reserve_complete_local_legends_without_changing_data(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, renderer: ModuleType,
    language: AppLanguage, dpi: int, landscape: bool,
) -> None:
    dataset = _dataset()
    before = deepcopy(dataset)
    geometry_records = []
    original = renderer._draw_chart_page

    def capture(*args: Any, **kwargs: Any) -> None:
        geometry_records.append((args[1], args[7], args[9]))
        original(*args, **kwargs)

    monkeypatch.setattr(renderer, '_draw_chart_page', capture)
    output = tmp_path / 'production.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        renderer.render_chart_pages(PageCanvas(writer, painter, language),
                                    _report('opus' if renderer is enhanced else 'standard'), dataset, language)
    finally:
        painter.end()
    with fitz.open(output) as document:
        assert len(document) == len(geometry_records) > 1
        for page, (geometry, panels, ranges) in zip(document, geometry_records, strict=True):
            assert geometry.legend_rect.bottom() <= geometry.note_rect.top() + 0.01
            assert geometry.legend_rect.top() > geometry.plot_rect.bottom()
            for rect, (_name, curves) in zip(geometry.panel_rects, panels, strict=True):
                layout = curve_legend_layout(rect.width(), curves, ranges, language, writer)
                assert layout.height <= geometry.legend_rect.height()
                for row in layout.rows:
                    assert _normalized(row.text) in _normalized(page.get_text())
    assert np.array_equal(dataset.depth, before.depth)
    for identifier, curve in dataset.curves.items():
        assert np.array_equal(curve.values, before.curves[identifier].values)
        assert curve.metadata == before.curves[identifier].metadata


@pytest.mark.parametrize('width', [0.0, 21.0, -1.0, float('inf'), float('nan')])
def test_invalid_width_is_rejected(qapp: object, tmp_path: Path, width: float) -> None:
    writer = QPdfWriter(str(tmp_path / 'invalid.pdf'))
    with pytest.raises(ValueError, match='width'):
        curve_legend_layout(width, (), {}, AppLanguage.EN, writer)


def test_missing_range_preserves_original_curve_color_index(qapp: object, tmp_path: Path) -> None:
    dataset = _dataset()
    curves = tuple(dataset.curves.values())[:3]
    writer = QPdfWriter(str(tmp_path / 'sparse.pdf'))
    layout = curve_legend_layout(160, curves, {curves[2].metadata.curve_id: (1, 2)}, AppLanguage.EN, writer)
    assert [row.curve_index for row in layout.rows] == [2]
    assert layout.rows[0].top == 0


def test_supplementary_unicode_survives_qt_utf16_line_offsets(qapp: object, tmp_path: Path) -> None:
    dataset = _dataset()
    curve = dataset.curves['WH']
    curve.metadata = replace(curve.metadata, unit='m³/🧪 test unit with supplementary Unicode')
    writer = QPdfWriter(str(tmp_path / 'unicode.pdf'))
    layout = curve_legend_layout(80, (curve,), {'WH': (1, 2)}, AppLanguage.EN, writer)
    assert _normalized(''.join(layout.rows[0].lines)) == _normalized(layout.rows[0].text)
    assert '🧪' in ''.join(layout.rows[0].lines)


def test_pagination_rechecks_ranges_after_the_page_count_changes(qapp: object, tmp_path: Path) -> None:
    from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage
    dataset = _dataset()
    curves = tuple(dataset.curves.values())[:5]
    writer = QPdfWriter(str(tmp_path / 'replan.pdf'))
    available_heights = []

    def planner(low: float, high: float, available: float) -> tuple[DepthPage, ...]:
        available_heights.append(available)
        count = min(len(available_heights), 2)
        return tuple(DepthPage(index, index + 1, 1000, available) for index in range(count))

    def ranges(page: DepthPage) -> dict[str, tuple[float, float]]:
        limits = (-1.234e-120, 9.876e120) if page.top_depth else (1.0, 2.0)
        return {curve.metadata.curve_id: limits for curve in curves}

    pages, height = layout_module.fit_curve_legend_pages(
        0, 2, 700, (100,), (('total', curves),), AppLanguage.EN, writer, {}, planner, ranges,
    )
    assert len(available_heights) >= 2
    assert available_heights == sorted(available_heights, reverse=True)
    assert len(pages) == 2
    for page in pages:
        assert curve_legend_layout(100, curves, ranges(page), AppLanguage.EN, writer).height + 7 <= height
