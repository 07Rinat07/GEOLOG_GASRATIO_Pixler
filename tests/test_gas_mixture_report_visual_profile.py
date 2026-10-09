from base64 import b64decode
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from unicodedata import normalize

import fitz
import numpy as np
from PIL import Image
import pytest
from PySide6.QtGui import QPdfWriter

from geoworkbench.printing import gas_mixture_ramp_report as ramp
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_gas_mixture_ramp_report import _session


def _normalized(text: str) -> str:
    return ''.join(normalize('NFKC', text).split())


def _page_body_text(page: fitz.Page) -> str:
    blocks = [block for block in page.get_text('dict')['blocks'] if 'lines' in block]
    footer_top = page.rect.height - 54
    footer = [block for block in blocks if block['bbox'][1] >= footer_top]
    footer_text = ''.join(span['text'] for block in footer for line in block['lines'] for span in line['spans'])
    assert 'DIGITAL GEOLOG' in footer_text
    assert any(f'{label} {page.number + 1}' in footer_text for label in ('Страница', 'Бет', 'Page'))
    return '\n'.join(span['text'] for block in blocks if block not in footer
                     for line in block['lines'] for span in line['spans'])


def test_pdf_body_extraction_keeps_numbers_in_cross_page_warning() -> None:
    with fitz.open() as pdf:
        for index, body in enumerate(('Warning: C2 has 2 samples;', 'all 3 values are retained.')):
            page = pdf.new_page(width=842, height=595)
            page.insert_text((90, 100), body)
            page.insert_text((40, 560), 'DIGITAL GEOLOG')
            page.insert_text((746, 560), f'Page {index + 1}')
        text = _normalized('\n'.join(_page_body_text(page) for page in pdf))
        assert text == _normalized('Warning: C2 has 2 samples; all 3 values are retained.')


def _profile(custom: bool):
    profile = modern_oilfield_report_profile()
    if not custom:
        return profile
    return replace(profile, palette=replace(profile.palette, page='#fff8ed', text='#281846',
        text_secondary='#423c71', text_muted='#675a38', accent='#751635', accent_soft='#f9e1c8',
        border='#b46622', border_strong='#715222', table_header='#d2c2e8'),
        typography=replace(profile.typography, title_pt=24, section_pt=13, body_pt=10,
                           table_pt=9, caption_pt=8))


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('include_chart', [False, True])
@pytest.mark.parametrize('custom', [False, True])
def test_actual_ramp_pdf_uses_shared_typography_palette_and_hides_audit_time(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    language: AppLanguage, dpi: int, include_chart: bool, custom: bool,
) -> None:
    profile = _profile(custom)
    monkeypatch.setattr(ramp, 'modern_oilfield_report_profile', lambda: profile)
    class Writer(QPdfWriter):
        def setResolution(self, resolution: int) -> None:  # noqa: N802 - Qt override
            super().setResolution(dpi)
    monkeypatch.setattr(ramp, 'QPdfWriter', Writer)
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    before = deepcopy(dataset)
    report = ramp.build_gas_mixture_ramp_report(session)
    before_report = deepcopy(report)
    target = ramp.export_gas_mixture_ramp_pdf(report, tmp_path / 'ramp.pdf',
                                             language=language, include_chart=include_chart)
    with fitz.open(target) as pdf:
        text = _normalized('\n'.join(_page_body_text(page) for page in pdf))
        labels = ramp._labels(language)
        for value in (profile.brand_wordmark, labels['title'], labels['composition'], labels['limitations'],
                      report.project_name, report.well_name, report.dataset_name, 'ISO 6974-1:2012',
                      *[item.mnemonic for item in report.components], *[name for name, _ in report.pixler_ratios],
                      *ramp.localized_ramp_warnings(report.warnings, language)):
            assert _normalized(value) in text
        for component in report.components:
            row = (f'{component.mnemonic}{component.baseline_value:.6g}'
                   f'{component.representative_value:.6g}{component.composition_percent:.2f}%'
                   f'{component.peak_value:.6g}')
            assert _normalized(row) in text
        for name, value in report.pixler_ratios:
            assert _normalized(f'{name}{value:.4g}') in text
        assert _normalized(report.generated_at) not in text
        spans = [span for page in pdf for block in page.get_text('dict')['blocks'] if 'lines' in block
                 for line in block['lines'] for span in line['spans']]
        for value, size in ((labels['title'], profile.typography.title_pt),
                            (labels['composition'], profile.typography.section_pt),
                            ('C1/C2', profile.typography.table_pt)):
            role_text = ''.join(span['text'] for span in spans if span['size'] == pytest.approx(size, abs=0.55))
            assert _normalized(value) in _normalized(role_text)
        text_colours = {span['color'] for span in spans}
        for colour in (profile.palette.text, profile.palette.text_muted, profile.palette.accent):
            assert int(colour[1:], 16) in text_colours
        fills = [drawing['fill'] for page in pdf for drawing in page.get_drawings() if drawing['fill']]
        header = tuple(int(profile.palette.table_header[index:index + 2], 16) / 255 for index in (1, 3, 5))
        assert any(fill == pytest.approx(header, abs=0.005) for fill in fills)
        for page in pdf:
            assert (page.rect.width > page.rect.height) == include_chart
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        assert (page.rect + (-0.5, -0.5, 0.5, 0.5)).contains(fitz.Rect(span['bbox']))
    assert report == before_report
    np.testing.assert_array_equal(dataset.depth, before.depth)
    for identifier, curve in dataset.curves.items():
        np.testing.assert_array_equal(curve.values, before.curves[identifier].values)
        assert curve.metadata == before.curves[identifier].metadata


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('custom', [False, True])
def test_ramp_chart_neutral_palette_keeps_all_five_component_lines(
    qapp: object, monkeypatch: pytest.MonkeyPatch, language: AppLanguage, custom: bool,
) -> None:
    profile = _profile(custom)
    monkeypatch.setattr(ramp, 'modern_oilfield_report_profile', lambda: profile)
    report = ramp.build_gas_mixture_ramp_report(_session())
    before = deepcopy(report)
    uri = ramp._chart_data_uri(report, language)
    pixels = np.asarray(Image.open(BytesIO(b64decode(uri.split(',', 1)[1]))).convert('RGB'))
    assert pixels.shape == (650, 1500, 3)
    for colour in (profile.palette.page, profile.palette.text, profile.palette.text_secondary):
        rgb = tuple(int(colour[index:index + 2], 16) for index in (1, 3, 5))
        assert np.count_nonzero(np.all(pixels == rgb, axis=2)) > 10
    # Fractional profile rule widths change antialias coverage. Check the actual
    # raster against independently painted frame/grid samples at the same DPI.
    from PySide6.QtCore import QLineF, QRectF
    from PySide6.QtGui import QColor, QImage, QPainter, QPen
    reference = QImage(1500, 650, QImage.Format.Format_ARGB32_Premultiplied)
    reference.fill(QColor(profile.palette.page))
    painter = QPainter(reference)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor(profile.palette.border_strong), profile.layout.strong_rule_pt * reference.logicalDpiY() / 72))
    painter.drawRect(QRectF(90, 70, 1320, 480))
    painter.setPen(QPen(QColor(profile.palette.border), profile.layout.thin_rule_pt * reference.logicalDpiY() / 72))
    for x in (90, 354):
        painter.drawLine(QLineF(x, 70, x, 550))
    painter.end()
    for x in (89, 354):
        expected = reference.pixelColor(x, 125)
        np.testing.assert_array_equal(pixels[125, x], (expected.red(), expected.green(), expected.blue()))
    plot_pixels = pixels[72:548, 92:1408]
    for colour in ramp._COLORS.values():
        rgb = tuple(int(colour[index:index + 2], 16) for index in (1, 3, 5))
        assert np.count_nonzero(np.all(plot_pixels == rgb, axis=2)) > 30
    assert report == before


@pytest.mark.parametrize('phase', ['font', 'print'])
def test_ramp_adapter_failure_preserves_existing_pdf(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    report = ramp.build_gas_mixture_ramp_report(_session())
    target = tmp_path / 'existing.pdf'
    target.write_bytes(b'original client file')
    def fail(document: object) -> None:
        raise RuntimeError('layout failure')
    if phase == 'font':
        from geoworkbench.printing import hydrocarbon_interpretation_pdf_text as pdf_text
        monkeypatch.setattr(pdf_text, 'apply_explicit_rich_text_font_sizes', fail)
    else:
        monkeypatch.setattr(ramp, 'render_report_html', lambda *args, **kwargs: fail(args[0]))
    with pytest.raises(ramp.GasMixtureRampReportError):
        ramp.export_gas_mixture_ramp_pdf(report, target, include_chart=False, overwrite=True)
    assert target.read_bytes() == b'original client file'
    assert list(tmp_path.iterdir()) == [target]
