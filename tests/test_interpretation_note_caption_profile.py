from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from unicodedata import normalize

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as standard
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing import interpretation_note_layout as notes
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage, chart_geometry
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_interpretation_chart_readability import _dataset, _report, _normalized
from test_interpretation_text_physical_dpi import _spans


@pytest.mark.parametrize('renderer', [standard, enhanced])
@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('landscape', [False, True])
def test_complete_profile_caption_notes_fit_above_footer_in_production_pdf(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, renderer: ModuleType,
    language: AppLanguage, dpi: int, landscape: bool,
) -> None:
    profile = modern_oilfield_report_profile()
    profile = replace(profile, typography=replace(profile.typography, caption_pt=9.0))
    for module in (standard, enhanced, notes):
        monkeypatch.setattr(module, 'modern_oilfield_report_profile', lambda: profile)
    dataset = _dataset()
    before = deepcopy(dataset)
    output = tmp_path / 'chart.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape
                              else QPageLayout.Orientation.Portrait)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        canvas = PageCanvas(writer, painter, language)
        note = standard._labels(language)['note']
        height = notes.interpretation_note_height(note, canvas.content_rect.width(), writer)
        bottom = canvas.content_rect.bottom()
        renderer.render_chart_pages(canvas, _report('opus' if renderer is enhanced else 'standard'),
                                    dataset, language)
    finally:
        painter.end()
    with fitz.open(output) as document:
        assert len(document) > 1
        for page in document:
            assert _normalized(note) in _normalized(normalize("NFKC", page.get_text()))
            spans = [span for span in _spans(page) if bottom-height-0.5 <= span['bbox'][1] < bottom]
            assert spans
            assert all(span['size'] == pytest.approx(9.0, abs=0.08) for span in spans)
            assert all(span['bbox'][3] <= bottom+0.5 for span in spans)
            traces = [draw for draw in page.get_drawings() if draw['width'] == pytest.approx(1.25, abs=0.03)]
            assert traces and all(draw['rect'].y1 < bottom-height for draw in traces)
    assert np.array_equal(dataset.depth, before.depth)
    for key, curve in dataset.curves.items():
        assert np.array_equal(curve.values, before.curves[key].values)
        assert curve.metadata == before.curves[key].metadata


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
def test_empty_geology_tracks_use_readable_caption_role_and_full_localized_message(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: AppLanguage, dpi: int,
) -> None:
    profile = modern_oilfield_report_profile()
    profile = replace(profile, typography=replace(profile.typography, caption_pt=9.0))
    monkeypatch.setattr(enhanced, 'modern_oilfield_report_profile', lambda: profile)
    output = tmp_path / 'empty.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        page = DepthPage(1000, 1100, 1000, 400)
        geometry = chart_geometry(QRectF(0, 0, 500, 700), page, 3, geology_track_count=2)
        enhanced._draw_geology_tracks(painter, geometry, page, None, ('cuttings','lba'),
                                     ('cuttings','lba'), language)
    finally:
        painter.end()
    message = {AppLanguage.RU:'Нет данных', AppLanguage.KK:'Дерек жоқ', AppLanguage.EN:'No data'}[language]
    with fitz.open(output) as document:
        spans = [span for span in _spans(document[0]) if span['bbox'][1] > 150]
        assert _normalized(''.join(span['text'] for span in spans)).count(_normalized(message)) == 2
        assert all(span['size'] == pytest.approx(9.0, abs=0.08) for span in spans)
