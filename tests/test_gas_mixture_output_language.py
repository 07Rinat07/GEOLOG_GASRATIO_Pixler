from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unicodedata import normalize

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter
from PySide6.QtPrintSupport import QPrinter

from geoworkbench.printing import gas_mixture_ramp_report as ramp
from geoworkbench.printing.gas_mixture_report_i18n import (
    localized_ramp_time_label, localized_ramp_warnings, ramp_missing_time_warning, ramp_standard_warnings,
)
from geoworkbench.services.localization import AppLanguage
from test_gas_mixture_ramp_report import _session


def _normalized(text):
    return ''.join(normalize('NFKC', text).split())


def _axis_session(kind):
    session = _session()
    dataset = session.current_dataset
    index = next(iter(dataset.indexes.values()))
    if kind == 'missing':
        dataset.indexes.clear()
    elif kind == 'datetime':
        index.values = np.datetime64('2026-10-09T12:00:00') + np.arange(60).astype('timedelta64[s]')
    elif kind == 'vendor':
        index.mnemonic = 'Client уақыт <&>'
        index.unit = 'ms'
    return session


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('axis', ['numeric', 'datetime', 'missing', 'vendor'])
@pytest.mark.parametrize('dpi', [72, 300, 600])
@pytest.mark.parametrize('include_chart', [False, True])
@pytest.mark.parametrize('device_kind', ['writer', 'printer'])
def test_actual_ramp_exports_use_one_language_and_preserve_audit(
    qapp, tmp_path: Path, monkeypatch, language, axis, dpi, include_chart, device_kind,
):
    session = _axis_session(axis)
    dataset = session.current_dataset
    before_dataset = deepcopy(dataset)
    report = ramp.build_gas_mixture_ramp_report(session)
    custom_warning = 'Client note <&> Әлия: C2 has 2 samples.'
    report = replace(report, warnings=report.warnings + (custom_warning,))
    before = deepcopy(report)
    labels = ramp._labels(language)
    expected_warnings = localized_ramp_warnings(report.warnings, language)
    html = ramp.gas_mixture_ramp_html(report, language, include_chart=False)
    assert f'<th>{labels["component"]}</th>' in html
    assert 'Client note &lt;&amp;&gt;' in html
    requested_text = []
    original_draw = ramp._draw_chart_text
    def capture(painter, rect, text, size, **kwargs):
        requested_text.append(text)
        original_draw(painter, rect, text, size, **kwargs)
    monkeypatch.setattr(ramp, '_draw_chart_text', capture)
    target = tmp_path / 'ramp.pdf'
    if device_kind == 'writer':
        class Writer(QPdfWriter):
            def setResolution(self, resolution):  # noqa: N802 - Qt override
                super().setResolution(dpi)
        monkeypatch.setattr(ramp, 'QPdfWriter', Writer)
        ramp.export_gas_mixture_ramp_pdf(report, target, language=language, include_chart=include_chart)
    else:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(target))
        printer.setResolution(dpi)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape if include_chart else QPageLayout.Orientation.Portrait)
        printer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
        ramp.render_gas_mixture_ramp_report(printer, report, language=language, include_chart=include_chart)
    with fitz.open(target) as pdf:
        text = _normalized('\n'.join(page.get_text() for page in pdf))
        for value in (labels['title'], labels['component'], labels['composition'], labels['limitations'],
                      labels[report.interpretation_code], labels[report.confidence], *expected_warnings):
            assert _normalized(value) in text
        if language != AppLanguage.RU:
            for warning in report.warnings[:-1]:
                assert _normalized(warning) not in text
        if language == AppLanguage.EN:
            assert 'Компонент' not in text
        for component in report.components:
            row = f'{component.mnemonic}{component.baseline_value:.6g}{component.representative_value:.6g}{component.composition_percent:.2f}%{component.peak_value:.6g}'
            assert _normalized(row) in text
        for name, value in report.pixler_ratios:
            assert _normalized(f'{name}{value:.4g}') in text
        footer_label = {AppLanguage.RU:'Страница', AppLanguage.KK:'Бет', AppLanguage.EN:'Page'}[language]
        for page in pdf:
            assert _normalized(f'{footer_label} {page.number + 1}') in _normalized(page.get_text())
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        assert (page.rect + (-.5, -.5, .5, .5)).contains(fitz.Rect(span['bbox']))
    if include_chart:
        assert requested_text[0] == labels['chart']
        assert requested_text[1] == labels['chart_scale']
        assert requested_text[-1] == localized_ramp_time_label(report.time_label, language)
    assert report == before
    assert dataset.name == before_dataset.name
    np.testing.assert_array_equal(dataset.depth, before_dataset.depth)
    for key, curve in dataset.curves.items():
        assert curve.metadata == before_dataset.curves[key].metadata
        np.testing.assert_array_equal(curve.values, before_dataset.curves[key].values)
    for key, index in dataset.indexes.items():
        assert index.mnemonic == before_dataset.indexes[key].mnemonic
        np.testing.assert_array_equal(index.values, before_dataset.indexes[key].values)


@pytest.mark.parametrize('language', list(AppLanguage))
def test_known_messages_translate_without_changing_unknown_client_text(language):
    original = (*ramp_standard_warnings(), ramp_missing_time_warning(), 'Vendor <&> предупреждение')
    localized = localized_ramp_warnings(original, language)
    assert len(localized) == len(original)
    assert localized[-1] == original[-1]
    assert (localized[:5] == original[:5]) == (language == AppLanguage.RU)
    assert localized_ramp_time_label('Client время, ms', language) == 'Client время, ms'
