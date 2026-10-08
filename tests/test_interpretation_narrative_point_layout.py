from dataclasses import replace
from pathlib import Path
from unicodedata import normalize

import fitz
import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtPrintSupport import QPrinter

from geoworkbench.printing import hydrocarbon_interpretation_pdf_text as text_renderer
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage


LABELS = {
    AppLanguage.RU: ('Описание интервала', 'Газовый состав породы', 'Глубина'),
    AppLanguage.KK: ('Аралықтың сипаттамасы', 'Тау жынысының газ құрамы', 'Тереңдік'),
    AppLanguage.EN: ('Interval description', 'Rock gas composition', 'Depth'),
}


def _normalized(value: str) -> str:
    return ''.join(normalize('NFKC', value).split())


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('custom', [False, True])
@pytest.mark.parametrize('compact', [False, True])
def test_real_rich_text_uses_physical_profile_sizes_and_measured_bounds(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    language: AppLanguage, dpi: int, custom: bool, compact: bool,
) -> None:
    profile = modern_oilfield_report_profile()
    if custom:
        profile = replace(profile, typography=replace(profile.typography, title_pt=20,
                          section_pt=13, body_pt=10, table_pt=9))
    monkeypatch.setattr(text_renderer, 'modern_oilfield_report_profile', lambda: profile)
    title, body, header = LABELS[language]
    fragment = (f'<h1>{title}</h1><h2>Section</h2><p>{body}</p>'
                f'<table class="sample-table"><tr><th>{header}</th></tr>'
                '<tr><td>1305–1320 m</td></tr></table>')
    # Existing source-table classes must not defeat the compact-cell fallback.
    source_style = f'.sample-table {{ font-size: {profile.typography.table_pt}pt; }}'
    document, height = text_renderer._html_document(source_style, fragment, 300,
                                                   table=True, compact_table=compact)
    assert document.documentLayout().paintDevice().logicalDpiY() == 72
    assert height == pytest.approx(document.size().height())
    output = tmp_path / 'narrative.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(writer)
    assert painter.isActive()
    painter.scale(dpi / 72, dpi / 72)
    painter.translate(30, 30)
    document.drawContents(painter, QRectF(0, 0, 300, height))
    painter.end()
    with fitz.open(output) as pdf:
        page = pdf[0]
        extracted = _normalized(page.get_text())
        spans = [span for block in page.get_text('dict')['blocks'] if 'lines' in block
                 for line in block['lines'] for span in line['spans']]
        expected = [(title, profile.typography.title_pt), ('Section', profile.typography.section_pt),
                    (body, profile.typography.body_pt), (header, 6.8 if compact else profile.typography.table_pt),
                    ('1305–1320 m', 6.8 if compact else profile.typography.table_pt)]
        for value, size in expected:
            assert _normalized(value) in extracted
            matching = [span for span in spans if _normalized(span['text']) in _normalized(value)]
            assert matching
            assert all(span['size'] == pytest.approx(size, abs=0.55) for span in matching)
        for span in spans:
            bounds = fitz.Rect(span['bbox'])
            assert bounds.x0 >= 29.5 and bounds.x1 <= 330.5
            assert bounds.y0 >= 29.5 and bounds.y1 <= 30 + height + 0.5


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('landscape', [False, True])
@pytest.mark.parametrize('printer_device', [False, True])
def test_paginated_narrative_repeats_headers_and_preserves_every_row(
    qapp: object, tmp_path: Path, language: AppLanguage, landscape: bool, printer_device: bool,
) -> None:
    title, body, header = LABELS[language]
    output = tmp_path / 'table.pdf'
    if printer_device:
        device = QPrinter(QPrinter.PrinterMode.HighResolution)
        device.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        device.setOutputFileName(str(output))
    else:
        device = QPdfWriter(str(output))
    device.setResolution(600)
    device.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    device.setPageOrientation(QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait)
    device.setPageMargins(QMarginsF(14, 14, 14, 14))
    rows = ''.join(f'<tr><td>ROW-{index:03d}</td><td>{body}</td></tr>' for index in range(120))
    html = (f'<html><body><h2>{title}</h2><table><thead><tr><th>{header}</th><th>Description</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></body></html>')
    painter = QPainter(device)
    assert painter.isActive()
    try:
        painter.scale(device.logicalDpiX() / 72, device.logicalDpiY() / 72)
        canvas = PageCanvas(device, painter, language)
        canvas.new_page()
        text_renderer.render_report_html(canvas, html, leading_block_count=0, start_body_on_new_page=False)
    finally:
        painter.end()
    with fitz.open(output) as pdf:
        assert len(pdf) > 1
        text = '\n'.join(page.get_text() for page in pdf)
        assert _normalized(title) in _normalized(text)
        for index in range(120):
            assert text.count(f'ROW-{index:03d}') == 1
        for page in pdf:
            assert _normalized(header) in _normalized(page.get_text())
            # Content stays above the footer; page margins are physical millimetres.
            rows_on_page = [span for block in page.get_text('dict')['blocks'] if 'lines' in block
                            for line in block['lines'] for span in line['spans'] if 'ROW-' in span['text']]
            assert rows_on_page
            assert all(span['bbox'][3] < page.rect.height - 14 * 72 / 25.4 - 15 for span in rows_on_page)


def test_explicit_heading_sizes_preserve_inline_styles_and_relative_superscripts(qapp: object) -> None:
    from PySide6.QtGui import QTextCharFormat

    document, _ = text_renderer._html_document(
        '', '<h1><a href="https://example.org">Heading</a> <i>Italic</i></h1>'
        '<p><b>Bold</b> CO<sub>2</sub> m<sup>3</sup></p>', 300,
    )
    formats = {}
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            formats[fragment.text()] = fragment.charFormat()
            iterator += 1
        block = block.next()
    assert formats['Heading'].anchorHref() == 'https://example.org'
    assert formats['Heading'].fontWeight() == 700
    assert formats['Italic'].fontItalic()
    assert formats['Bold'].fontWeight() == 700
    assert formats['2'].verticalAlignment() == QTextCharFormat.VerticalAlignment.AlignSubScript
    assert formats['3'].verticalAlignment() == QTextCharFormat.VerticalAlignment.AlignSuperScript
