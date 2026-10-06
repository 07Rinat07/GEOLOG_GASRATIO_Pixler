from dataclasses import replace
from copy import deepcopy

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.domain.depth_interval import DepthInterval
from geoworkbench.domain.report_composition import (
    InterpretationReportComposition, report_header_fields, with_report_header_fields,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import PAGE_FOOTER_HEIGHT
from geoworkbench.printing.hydrocarbon_interpretation_report import export_hydrocarbon_interpretation_pdf
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    default_interpretation_report_identity, identity_with_report_header_fields, report_header_fields_from_identity,
)
from geoworkbench.printing.report_document_control import report_document_control
from geoworkbench.printing.report_visual_system import REPORT_BRAND_WORDMARK
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_charts import _session_with_report_curves
from test_interpretation_report_identity import _manual_identity


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('profile', ['standard', 'opus'])
@pytest.mark.parametrize('date', ['', '07.10.2026'])
@pytest.mark.parametrize('orientation', [QPageLayout.Orientation.Portrait, QPageLayout.Orientation.Landscape])
def test_saved_control_repeats_on_every_production_pdf_page(qapp, tmp_path, language, profile, date, orientation):
    session = _session_with_report_curves(depth_span=30, samples=61)
    identity = replace(_manual_identity(), document_number='DOC-42', revision='07', document_status='Approved',
                       confidentiality='Internal', report_date=date, interval='stale interval')
    dataset_id = session.current_dataset.dataset_id
    session.report_compositions[dataset_id] = with_report_header_fields(
        InterpretationReportComposition(), language.value, report_header_fields_from_identity(identity, profile))
    package = tmp_path / 'saved.geologpkg'
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    composition = restored.report_compositions[dataset_id]
    before = deepcopy(composition)
    report = replace(build_hydrocarbon_interpretation_report(restored), report_profile=profile,
                     analysis_depth_interval=DepthInterval(1305, 1320))
    resolved = identity_with_report_header_fields(default_interpretation_report_identity(report, language),
                                                report_header_fields(composition, language.value, profile))
    dataset = restored.current_dataset
    originals = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    depth = dataset.depth.copy()
    target = export_hydrocarbon_interpretation_pdf(report, tmp_path / 'controlled.pdf', language=language,
        dataset=dataset, include_chart=True, identity=resolved, orientation=orientation)
    with fitz.open(target) as document:
        assert len(document) >= 3
        for index, page in enumerate(document):
            footer = page.get_text(clip=fitz.Rect(0, page.rect.height - 70, page.rect.width, page.rect.height))
            for value in (REPORT_BRAND_WORDMARK, 'DOC-42', '07', 'Approved', 'Internal'):
                assert value in footer
            page_label = {AppLanguage.RU: 'Страница', AppLanguage.KK: 'Бет', AppLanguage.EN: 'Page'}[language]
            assert f'{page_label} {index + 1}' in footer
            assert 'stale interval' not in footer and report.generated_at not in footer
            assert not date or date not in footer
        full_text = '\n'.join(page.get_text() for page in document)
        assert 'stale interval' not in full_text
        assert (date in full_text) if date else '01.08.2026' not in full_text
    assert restored.report_compositions[dataset_id] == before
    np.testing.assert_array_equal(dataset.depth, depth)
    for key, values in originals.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)


@pytest.mark.parametrize('dpi', [72, 96, 144, 300, 600])
@pytest.mark.parametrize('width_mm', [25, 210])
def test_footer_text_is_bounded_and_physical_size_stable(qapp, tmp_path, monkeypatch, dpi, width_mm):
    identity = replace(_manual_identity(), document_number='Long document ' * 100,
                       confidentiality='Long confidentiality ' * 100)
    writer = QPdfWriter(str(tmp_path / 'footer.pdf'))
    writer.setResolution(dpi)
    writer.setPageSize(QPageSize(QSizeF(width_mm, 100), QPageSize.Unit.Millimeter))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    painter = QPainter(writer)
    painter.scale(dpi / 72, dpi / 72)
    canvas = PageCanvas(writer, painter, AppLanguage.KK, document_control=report_document_control(identity, AppLanguage.KK))
    captured = []
    original = canvas._draw_footer_text
    def capture(rect, text, font, **kwargs):
        captured.append((rect, text, font.pointSizeF() * dpi / 72))
        return original(rect, text, font, **kwargs)
    monkeypatch.setattr(canvas, '_draw_footer_text', capture)
    try:
        canvas.new_page()
        canvas.new_page()
    finally:
        painter.end()
    assert len(captured) == 6
    assert canvas.page_rect.height() - canvas.content_rect.height() == PAGE_FOOTER_HEIGHT + 14
    for rect, text, physical_points in captured:
        assert rect.top() > canvas.content_rect.bottom()
        assert rect.left() >= canvas.page_rect.left()
        assert rect.right() <= canvas.page_rect.right()
        assert rect.bottom() <= canvas.page_rect.bottom()
        assert physical_points == pytest.approx(canvas.visual.typography.footer_pt)
    with fitz.open(tmp_path / 'footer.pdf') as document:
        assert len(document) == 2
        for page in document:
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        assert span['bbox'][0] >= -0.5
                        assert span['bbox'][2] <= page.rect.width + 0.5
                        assert span['size'] == pytest.approx(canvas.visual.typography.footer_pt, abs=0.75)


def test_empty_footer_metadata_retains_existing_content_geometry(qapp, tmp_path):
    writer = QPdfWriter(str(tmp_path / 'empty.pdf'))
    painter = QPainter(writer)
    try:
        snapshot = report_document_control(replace(_manual_identity(), document_number='', revision='',
            document_status='', confidentiality='', report_date='07.10.2026'), AppLanguage.EN)
        canvas = PageCanvas(writer, painter, AppLanguage.EN, document_control=snapshot)
        assert canvas.footer_details == ''
        assert canvas.page_rect.height() - canvas.content_rect.height() == PAGE_FOOTER_HEIGHT
    finally:
        painter.end()
