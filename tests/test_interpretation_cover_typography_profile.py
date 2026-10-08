from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unicodedata import normalize

import fitz
import pytest
from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing import hydrocarbon_interpretation_pdf_cover as cover
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.report_document_control import report_document_control, resolved_report_identity
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_identity import _manual_identity, _report


TITLES = {
    AppLanguage.RU: ('Подробный геологический отчёт по результатам газового каротажа',
                     'Описание газового состава и выделенных перспективных интервалов'),
    AppLanguage.KK: ('Газ каротажы нәтижелері бойынша толық геологиялық есеп',
                     'Газ құрамының және бөлінген перспективалық аралықтардың сипаттамасы'),
    AppLanguage.EN: ('Detailed geological report on the results of mud gas logging',
                     'Description of gas composition and identified prospective intervals'),
}


def _normalized(value: str) -> str:
    return ''.join(normalize('NFKC', value).split())


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('landscape', [False, True])
@pytest.mark.parametrize('custom', [False, True])
def test_cover_uses_shared_roles_without_clipping_text_or_overlapping_sections(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    language: AppLanguage, dpi: int, landscape: bool, custom: bool,
) -> None:
    profile = modern_oilfield_report_profile()
    if custom:
        profile = replace(profile, typography=replace(profile.typography, title_pt=24,
                          subtitle_pt=11, body_pt=10, caption_pt=8))
    monkeypatch.setattr(cover, 'modern_oilfield_report_profile', lambda: profile)
    report = _report()
    title, subtitle = TITLES[language]
    identity = replace(_manual_identity(), report_title=title, report_subtitle=subtitle)
    before_report, before_identity = deepcopy(report), deepcopy(identity)
    control = report_document_control(resolved_report_identity(report, identity, language), language)
    output = tmp_path / 'cover.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait)
    writer.setPageMargins(QMarginsF(14, 14, 14, 14))
    painter = QPainter(writer)
    assert painter.isActive()
    try:
        painter.scale(dpi / 72, dpi / 72)
        canvas = PageCanvas(writer, painter, language)
        canvas.new_page()
        cover.render_report_cover(canvas, report, language, identity)
    finally:
        painter.end()
    with fitz.open(output) as pdf:
        assert len(pdf) == 1
        page = pdf[0]
        text = _normalized(page.get_text())
        spans = [span for block in page.get_text('dict')['blocks'] if 'lines' in block
                 for line in block['lines'] for span in line['spans']]
        for label, value in control.available_rows:
            assert _normalized(label) in text
            assert _normalized(value) in text
        for value in (title, subtitle, identity.confidentiality, identity.remarks,
                      cover._LABELS[language]['signature'], cover._LABELS[language]['footer']):
            assert _normalized(value) in text
        for value, size in ((title, profile.typography.title_pt),
                            (subtitle, profile.typography.subtitle_pt),
                            (identity.prepared_by, profile.typography.body_pt),
                            (identity.document_number, profile.typography.body_pt),
                            (identity.remarks, profile.typography.caption_pt)):
            role_text = ''.join(span['text'] for span in spans
                                if span['size'] == pytest.approx(size, abs=0.55))
            assert _normalized(value) in _normalized(role_text)
        margin = 14 * 72 / 25.4
        for span in spans:
            bounds = fitz.Rect(span['bbox'])
            assert margin - 1 <= bounds.x0 <= bounds.x1 <= page.rect.width - margin + 1
            assert margin - 1 <= bounds.y0 <= bounds.y1 <= page.rect.height - margin + 1
        # Independently extracted glyph bounds must not collide with another cell
        # or section. Complete-text assertions above also reject silent clipping.
        for index, first in enumerate(spans):
            for second in spans[index + 1:]:
                intersection = fitz.Rect(first['bbox']) & fitz.Rect(second['bbox'])
                assert intersection.is_empty or intersection.width <= 0.3 or intersection.height <= 0.3
        assert report.generated_at not in page.get_text()
    assert report == before_report
    assert identity == before_identity


@pytest.mark.parametrize('width', [0.0, -1.0, float('nan'), float('inf')])
def test_cover_text_layout_rejects_invalid_width(qapp: object, width: float) -> None:
    from geoworkbench.printing.interpretation_cover_text_layout import cover_text_layout
    from geoworkbench.printing.unicode_support import print_font

    with pytest.raises(ValueError, match='finite and positive'):
        cover_text_layout('Title', width, print_font(9, text='Title'), None)


def test_cover_text_layout_preserves_paragraph_breaks_and_supplementary_unicode(qapp: object) -> None:
    from geoworkbench.printing.interpretation_cover_text_layout import cover_text_layout
    from geoworkbench.printing.unicode_support import print_font

    text = 'Аралық 😀 1305–1320 m\n\nГазовый состав 🌍 интервала'
    layout = cover_text_layout(text, 55, print_font(9, text=text), None)
    assert _normalized(''.join(layout.lines)) == _normalized(text)
    assert layout.lines.count('') == 1
    assert len(layout.lines) > 3
