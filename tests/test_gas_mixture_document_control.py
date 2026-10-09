from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unicodedata import normalize

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtPrintSupport import QPrinter

from geoworkbench.printing import gas_mixture_ramp_report as ramp
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import InterpretationReportIdentity
from geoworkbench.printing.report_document_control import compact_report_footer
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_gas_mixture_ramp_report import _session


def _normalized(value):
    return ''.join(normalize('NFKC', value).split())


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('include_chart', [False, True])
@pytest.mark.parametrize('device_kind', ['writer', 'printer'])
@pytest.mark.parametrize('details_kind', ['default', 'full', 'long'])
def test_ramp_controlled_pdf_retains_full_values_and_repeated_footer(
    qapp, tmp_path: Path, monkeypatch, language, dpi, include_chart, device_kind, details_kind,
):
    visual = modern_oilfield_report_profile()
    visual = replace(visual, typography=replace(visual.typography, footer_pt=9),
                     palette=replace(visual.palette, text_muted='#654321'),
                     layout=replace(visual.layout, thin_rule_pt=1.2, strong_rule_pt=2.4))
    monkeypatch.setattr(ramp, 'modern_oilfield_report_profile', lambda: visual)
    session = _session()
    dataset = session.current_dataset
    before = deepcopy(dataset)
    report = ramp.build_gas_mixture_ramp_report(session)
    # Force repeated pages without changing any numeric calculations.
    report = replace(report, warnings=report.warnings + tuple(f'Warning {index}: C2 has 2 samples; all 3 values retained.' for index in range(25)))
    report_before = deepcopy(report)
    identity = None
    if details_kind != 'default':
        suffix = ' документ <&> ұңғыма well' * (18 if details_kind == 'long' else 1)
        identity = InterpretationReportIdentity(
            report_title=ramp._labels(language)['title'], report_subtitle='Sample C1–C5',
            project_name='Unrelated project', well_name='Unrelated well', dataset_name='Unrelated dataset',
            document_number='RAMP-17' + suffix, revision='03', document_status='Reviewed',
            report_date='' if details_kind == 'long' else '2026-10-09',
            prepared_by='Prepared <&> Әлия', checked_by='Checked <&> Ринат',
            approved_by='Approved <&> Engineer', confidentiality='Internal', remarks='Client notes <&>',
        )
    target = tmp_path / 'ramp.pdf'
    if device_kind == 'writer':
        class Writer(QPdfWriter):
            def setResolution(self, resolution):  # noqa: N802 - Qt override
                super().setResolution(dpi)
        monkeypatch.setattr(ramp, 'QPdfWriter', Writer)
        ramp.export_gas_mixture_ramp_pdf(report, target, language=language, include_chart=include_chart, identity=identity)
    else:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(target))
        printer.setResolution(dpi)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape if include_chart else QPageLayout.Orientation.Portrait)
        printer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
        ramp.render_gas_mixture_ramp_report(printer, report, language=language, include_chart=include_chart, identity=identity)
    control = ramp._ramp_document_control(report, language, identity)
    with fitz.open(target) as pdf:
        assert len(pdf) >= 2
        text = _normalized('\n'.join(page.get_text() for page in pdf))
        for _, value in control.available_rows:
            assert _normalized(value) in text
        for value in (*control.notes, *report.warnings, report.project_name, report.well_name, report.dataset_name):
            assert _normalized(value) in text
        assert _normalized(report.generated_at) not in text
        assert 'Unrelated' not in text
        for component in report.components:
            row = f'{component.mnemonic}{component.baseline_value:.6g}{component.representative_value:.6g}{component.composition_percent:.2f}%{component.peak_value:.6g}'
            assert _normalized(row) in text
        for page in pdf:
            if include_chart:
                for image in page.get_image_info():
                    assert fitz.Rect(33, 33, page.rect.width - 32, page.rect.height - 32).contains(fitz.Rect(image['bbox']))
            label = {AppLanguage.RU:'Страница', AppLanguage.KK:'Бет', AppLanguage.EN:'Page'}[language]
            spans = [span for block in page.get_text('dict')['blocks'] if 'lines' in block for line in block['lines'] for span in line['spans']]
            footer = [span for span in spans if span['bbox'][1] >= page.rect.height - 68]
            footer_text = _normalized(''.join(span['text'] for span in footer))
            assert _normalized(f'{label} {page.number + 1}') in footer_text
            assert 'DIGITALGEOLOG' in footer_text
            if control.footer_items:
                assert _normalized(compact_report_footer(control)) in footer_text
            assert all(span['color'] == int(visual.palette.text_muted[1:], 16) for span in footer)
            page_number = [span for span in footer if label in span['text']]
            assert page_number and all(span['size'] == pytest.approx(9, abs=.15) for span in page_number)
            for span in spans:
                assert span['bbox'][0] >= 33
                assert span['bbox'][2] <= page.rect.width - 32
                assert span['bbox'][3] <= page.rect.height - 32
    assert report == report_before
    assert dataset.name == before.name
    np.testing.assert_array_equal(dataset.depth, before.depth)
    for identifier, curve in dataset.curves.items():
        assert curve.metadata == before.curves[identifier].metadata
        np.testing.assert_array_equal(curve.values, before.curves[identifier].values)


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('grayscale', [False, True])
def test_ramp_raster_rules_share_profile_without_changing_component_paths(qapp, monkeypatch, language, grayscale):
    visual = modern_oilfield_report_profile(grayscale=grayscale)
    visual = replace(visual, layout=replace(visual.layout, thin_rule_pt=1.2, strong_rule_pt=2.4))
    monkeypatch.setattr(ramp, 'modern_oilfield_report_profile', lambda: visual)
    rectangles, grids, curves, legends = [], [], [], []
    class Painter(QPainter):
        def drawRect(self, rect):
            rectangles.append((self.pen(), rect, self.device().logicalDpiY()))
            super().drawRect(rect)
        def drawLine(self, line):
            (legends if line.y1() == 590 else grids).append(self.pen())
            super().drawLine(line)
        def drawPath(self, path):
            curves.append(self.pen())
            super().drawPath(path)
    monkeypatch.setattr(ramp, 'QPainter', Painter)
    report = ramp.build_gas_mixture_ramp_report(_session())
    before = deepcopy(report)
    assert ramp._chart_data_uri(report, language).startswith('data:image/png;base64,')
    pen, rect, dpi = rectangles[0]
    assert pen.widthF() == pytest.approx(2.4 * dpi / 72)
    assert (rect.x(), rect.y(), rect.width(), rect.height()) == (90, 70, 1320, 480)
    assert len(grids) == 12
    assert all(pen.widthF() == pytest.approx(1.2 * dpi / 72) for pen in grids)
    assert all(pen.color().name() == visual.palette.border for pen in grids)
    assert len(curves) == len(legends) == 5
    assert curves == legends
    assert all(pen.widthF() == 3 for pen in curves)
    assert report == before
