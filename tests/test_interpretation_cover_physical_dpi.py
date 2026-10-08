from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any
from unicodedata import normalize

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtPrintSupport import QPrinter

from geoworkbench.domain.depth_interval import DepthInterval
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_cover import _LABELS, render_report_cover
from geoworkbench.printing.hydrocarbon_interpretation_pdf_renderer import render_hydrocarbon_interpretation_report
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity, default_interpretation_report_identity,
)
from geoworkbench.printing.report_document_control import report_document_control, resolved_report_identity
from geoworkbench.services.hydrocarbon_interpretation import (
    HydrocarbonInterpretationReport, build_hydrocarbon_interpretation_report,
)
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_charts import _session_with_report_curves
from test_interpretation_report_identity import _manual_identity, _report


def _normalized(text: str) -> str:
    return ''.join(normalize('NFKC', text).split())


def _spans(page: fitz.Page) -> list[dict[str, Any]]:
    return [span for block in page.get_text('dict')['blocks'] if 'lines' in block
            for line in block['lines'] for span in line['spans']]


def _cover_pdf(
    device: QPdfWriter | QPrinter, report: HydrocarbonInterpretationReport,
    identity: InterpretationReportIdentity, language: AppLanguage,
) -> None:
    painter = QPainter(device)
    assert painter.isActive()
    try:
        painter.scale(device.logicalDpiX() / 72.0, device.logicalDpiY() / 72.0)
        canvas = PageCanvas(device, painter, language,
                            document_control=report_document_control(identity, language))
        canvas.new_page()
        render_report_cover(canvas, report, language, identity)
    finally:
        painter.end()


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('profile', ['standard', 'opus'])
@pytest.mark.parametrize('landscape', [False, True])
@pytest.mark.parametrize('date', ['', '08.10.2026'])
def test_real_cover_retains_72_dpi_text_sizes_and_bounds_at_print_resolutions(
    qapp: object, tmp_path: Path, language: AppLanguage, profile: str,
    landscape: bool, date: str,
) -> None:
    report = replace(_report(), report_profile=profile, analysis_depth_interval=DepthInterval(1250, 1350))
    defaults = default_interpretation_report_identity(report, language)
    identity = replace(_manual_identity(), report_title=defaults.report_title,
                       report_subtitle=defaults.report_subtitle, report_date=date)
    before_report, before_identity = deepcopy(report), deepcopy(identity)
    expected = resolved_report_identity(report, identity, language)
    snapshot = report_document_control(expected, language)
    reference = None
    for dpi in (72, 300, 600):
        target = tmp_path / f'cover-{dpi}.pdf'
        writer = QPdfWriter(str(target))
        writer.setResolution(dpi)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait)
        writer.setPageMargins(QMarginsF(14, 14, 14, 14))
        _cover_pdf(writer, report, identity, language)
        with fitz.open(target) as document:
            assert len(document) == 1
            page = document[0]
            text = _normalized(page.get_text())
            for value in (expected.report_title, expected.report_subtitle, *[value for _, value in snapshot.available_rows],
                          expected.confidentiality, expected.remarks, _LABELS[language]['footer']):
                assert _normalized(value) in text
            assert report.generated_at not in page.get_text()
            if not date:
                assert _normalized(_LABELS[language]['date']) not in text
            spans = _spans(page)
            assert spans and max(span['size'] for span in spans) <= 24.1
            for span in spans:
                bounds = fitz.Rect(span['bbox'])
                assert bounds.x0 >= 38.5
                assert bounds.x1 <= page.rect.width - 38.5
                assert bounds.y0 >= 38.5
                assert bounds.y1 <= page.rect.height - 38.5
            if reference is None:
                reference = spans
                continue
            assert [span['text'] for span in spans] == [span['text'] for span in reference]
            for actual, baseline in zip(spans, reference, strict=True):
                assert actual['size'] == pytest.approx(baseline['size'], abs=0.08)
                assert actual['bbox'] == pytest.approx(baseline['bbox'], abs=1.1)
    assert report == before_report
    assert identity == before_identity


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('landscape', [False, True])
def test_qprinter_pdf_cover_uses_the_same_physical_font_contract(
    qapp: object, tmp_path: Path, language: AppLanguage, landscape: bool,
) -> None:
    report = _report()
    identity = replace(_manual_identity(), report_title='Cover print contract')
    output = tmp_path / 'printer-cover.pdf'
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(output))
    printer.setResolution(600)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape else QPageLayout.Orientation.Portrait)
    printer.setPageMargins(QMarginsF(14, 14, 14, 14))
    _cover_pdf(printer, report, identity, language)
    with fitz.open(output) as document:
        text = document[0].get_text()
        for value in (identity.report_title, identity.document_number, identity.report_date,
                      identity.prepared_by, identity.checked_by, identity.approved_by):
            assert _normalized(value) in _normalized(text)
        spans = _spans(document[0])
        title = [span for span in spans if span['text'] == identity.report_title]
        assert title and all(span['size'] == pytest.approx(22, abs=0.1) for span in title)
        assert max(span['size'] for span in spans) <= 24.1


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('profile', ['standard', 'opus'])
def test_production_multipage_renderer_keeps_cover_control_and_source_data(
    qapp: object, tmp_path: Path, language: AppLanguage, profile: str,
) -> None:
    session = _session_with_report_curves(depth_span=30, samples=61)
    dataset = session.current_dataset
    assert dataset is not None
    before = deepcopy(dataset)
    report = replace(build_hydrocarbon_interpretation_report(session), report_profile=profile,
                     analysis_depth_interval=DepthInterval(1305, 1320))
    identity = replace(_manual_identity(), report_title='Client report', interval='stale interval', report_date='')
    expected = resolved_report_identity(report, identity, language)
    output = tmp_path / 'production.pdf'
    writer = QPdfWriter(str(output))
    writer.setResolution(600)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setPageMargins(QMarginsF(14, 14, 14, 14))
    render_hydrocarbon_interpretation_report(writer, report, dataset=dataset,
                                            include_chart=True, identity=identity, language=language)
    with fitz.open(output) as document:
        assert len(document) > 2
        text = document[0].get_text()
        for value in (identity.report_title, identity.project_name, identity.well_name, identity.document_number,
                      identity.prepared_by, identity.checked_by, identity.approved_by, expected.interval):
            assert _normalized(value) in _normalized(text)
        assert 'stale interval' not in text
        assert report.generated_at not in text
        assert _normalized(_LABELS[language]['date']) not in _normalized(text)
        assert max(span['size'] for span in _spans(document[0])) <= 24.1
    np.testing.assert_array_equal(dataset.depth, before.depth)
    for identifier, curve in dataset.curves.items():
        np.testing.assert_array_equal(curve.values, before.curves[identifier].values)
        assert curve.metadata == before.curves[identifier].metadata
