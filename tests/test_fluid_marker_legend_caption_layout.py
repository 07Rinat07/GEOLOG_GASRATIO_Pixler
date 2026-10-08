from copy import deepcopy
from dataclasses import replace
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace
from unicodedata import normalize

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing import fluid_marker_legend_layout as legends
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing import interpretation_note_layout as notes
from geoworkbench.printing.hydrocarbon_fluid_markers import all_fluid_marker_specs
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_interpretation_chart_readability import _dataset, _report, _normalized
from test_interpretation_text_physical_dpi import _spans


_HYPOTHESES = ('probable_gas', 'gas_condensate_or_high_api_oil', 'light_oil_high_gor',
               'heavy_or_residual_oil', 'indeterminate')


def _candidates() -> tuple[SimpleNamespace, ...]:
    return tuple(SimpleNamespace(top_depth=1000.0, bottom_depth=1350.0, fluid_hypothesis=value)
                 for value in _HYPOTHESES)


def _profile(monkeypatch: pytest.MonkeyPatch, size: float) -> None:
    profile = modern_oilfield_report_profile()
    profile = replace(profile, typography=replace(profile.typography, caption_pt=size))
    for module in (legends, enhanced, notes):
        monkeypatch.setattr(module, 'modern_oilfield_report_profile', lambda: profile)


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('width', [180.0, 360.0, 550.0])
@pytest.mark.parametrize('size', [7.2, 9.0])
def test_real_marker_legend_retains_all_labels_shapes_and_note_without_overlap(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: AppLanguage,
    dpi: int, width: float, size: float,
) -> None:
    _profile(monkeypatch, size)
    output = tmp_path / 'legend.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    specs = all_fluid_marker_specs()
    layout = legends.fluid_marker_legend_layout(width, specs, language, writer)
    for count in range(1, len(specs)+1):
        for subset in combinations(specs, count):
            assert legends.fluid_marker_legend_layout(width, subset, language, writer).height <= layout.height
    candidates = _candidates()
    before = deepcopy(candidates)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        enhanced._draw_fluid_marker_legend(painter, QRectF(20, 40, width, layout.height),
                                           DepthPage(1000, 1350, 1000, 400), candidates,
                                           language, fallback_note='unused')
    finally:
        painter.end()
    with fitz.open(output) as document:
        text = _normalized(normalize('NFKC', document[0].get_text()))
        for cell in layout.cells:
            assert _normalized(cell.text) in text
        assert _normalized(layout.note) in text
        spans = _spans(document[0])
        assert all(span['size'] == pytest.approx(7.0 if size == 7.2 else size, abs=0.08) for span in spans)
        assert all(19.5 <= span['bbox'][0] and span['bbox'][2] <= 20+width+0.5 and
                   39.5 <= span['bbox'][1] and span['bbox'][3] <= 40+layout.height+0.5 for span in spans)
        for first, second in combinations(spans, 2):
            assert not fitz.Rect(first['bbox']).intersects(fitz.Rect(second['bbox']))
        drawings = document[0].get_drawings()
        for spec in specs:
            color = tuple(int(spec.color[index:index+2],16)/255 for index in (1,3,5))
            glyphs = [draw for draw in drawings if draw['color'] and
                      all(abs(a-b)<0.002 for a,b in zip(draw['color'],color,strict=True))]
            assert glyphs
            cell = next(cell for cell in layout.cells if cell.spec == spec)
            first_line = min((span for span in spans if
                              20+cell.left+9 <= span['bbox'][0] < 20+cell.left+cell.width and
                              40+cell.top <= span['bbox'][1] < 40+cell.top+cell.height),
                             key=lambda span:span['bbox'][1])
            assert all(first_line['bbox'][1]-1 <= draw['rect'].y0+draw['rect'].height/2 <=
                       first_line['bbox'][3]+1 for draw in glyphs)
    assert candidates == before
    assert tuple(cell.spec for cell in layout.cells) == specs


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('landscape', [False, True])
def test_production_pdf_reserves_marker_legend_above_footer_and_preserves_candidates(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: AppLanguage,
    dpi: int, landscape: bool,
) -> None:
    _profile(monkeypatch, 9.0)
    dataset = _dataset()
    before = deepcopy(dataset)
    report = _report('opus')
    report.candidates = _candidates()
    candidates_before = deepcopy(report.candidates)
    output = tmp_path / 'chart.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageMargins(QMarginsF(0,0,0,0))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape
                              else QPageLayout.Orientation.Portrait)
    painter = QPainter(writer)
    try:
        painter.scale(dpi/72,dpi/72)
        canvas = PageCanvas(writer,painter,language)
        bottom = canvas.content_rect.bottom()
        layout = legends.fluid_marker_legend_layout(canvas.content_rect.width(),
                                                    all_fluid_marker_specs(),language,writer)
        enhanced.render_chart_pages(canvas,report,dataset,language)
    finally:
        painter.end()
    with fitz.open(output) as document:
        assert len(document)>1
        for page in document:
            text = _normalized(normalize('NFKC',page.get_text()))
            assert _normalized(layout.note) in text
            for cell in layout.cells:
                assert _normalized(cell.text) in text
            spans = [span for span in _spans(page) if bottom-layout.height-0.5 <= span['bbox'][1] < bottom]
            assert spans and all(span['size']==pytest.approx(9.0,abs=0.08) for span in spans)
            assert all(span['bbox'][3]<=bottom+0.5 for span in spans)
            traces = [draw for draw in page.get_drawings() if draw['width']==pytest.approx(1.25,abs=0.03)]
            assert traces and all(draw['rect'].y1<bottom-layout.height for draw in traces)
    assert report.candidates == candidates_before
    assert np.array_equal(dataset.depth,before.depth)
    for key,curve in dataset.curves.items():
        assert np.array_equal(curve.values,before.curves[key].values)
        assert curve.metadata == before.curves[key].metadata


@pytest.mark.parametrize('width', [0.0, -1.0, 14.0, float('nan'), float('inf')])
def test_invalid_marker_legend_width_is_rejected(qapp: object, tmp_path: Path, width: float) -> None:
    writer = QPdfWriter(str(tmp_path/'unused.pdf'))
    with pytest.raises(ValueError, match='width'):
        legends.fluid_marker_legend_layout(width, all_fluid_marker_specs(), AppLanguage.RU, writer)
