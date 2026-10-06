from copy import deepcopy

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, MasterlogColumnTemplate
from geoworkbench.domain.well_passport import WellPassport
from geoworkbench.printing import masterlog_renderer
from geoworkbench.printing.masterlog_document_control import masterlog_document_control_layout
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_renderer import export_masterlog_pdf, masterlog_page_ranges, masterlog_size_mm, paint_masterlog
from geoworkbench.printing.hydrocarbon_report_i18n import hydrocarbon_report_labels
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


def controlled_form(date=''):
    session = ProjectSession()
    dataset = Dataset('log', 'Logging', DatasetKind.GTI, DepthDomain.MD, np.linspace(100, 400, 301))
    dataset.upsert_curve('C1', np.linspace(1, 300, 301))
    dataset.headers = {'REPORT_DATE': 'Vendor date', 'DATE': 'Acquisition date'}
    session.add_dataset(dataset, 'Well A')
    controller = MasterlogTemplateController(session)
    template = controller.create('Controlled log')
    template.header_height_mm = 40
    template.columns = [MasterlogColumnTemplate('depth', 'Depth', 'depth', 25),
                        MasterlogColumnTemplate('gas', 'Methane', 'curves', 175, ['C1'])]
    controller.update_header_fields(template.template_id, {
        'header.document_number': 'DOC-42', 'header.revision': '07', 'header.status': 'Approved',
        'header.report_date': date, 'header.prepared_by': 'Engineer A', 'header.checked_by': 'Engineer B',
        'header.approved_by': 'Engineer C', 'header.confidentiality': 'Internal', 'header.interval': 'STALE RANGE',
    })
    return session, template


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('page_format', ['A4', 'A3', 'roll'])
@pytest.mark.parametrize('date', ['', '2026-09-30'])
def test_controlled_masterlog_pdf_after_reopen(qapp, tmp_path, monkeypatch, language, page_format, date):
    session, template = controlled_form(date)
    template.page_format = page_format
    package = tmp_path / 'controlled.geologpkg'
    ProjectController(session=session).save_project(package)
    session = ProjectController().open_project(package)
    template = session.project.masterlog_templates[template.template_id]
    before = deepcopy(template)
    original_depth = session.current_dataset.depth.copy()
    curve_id = next(iter(session.current_dataset.curves))
    original_curve = session.current_dataset.curves[curve_id].values.copy()
    settings = MasterlogOutputSettings(145, 355, language)
    captured = []
    original = masterlog_renderer._paint_columns
    def capture(painter, form, size, source, depth_range, columns, lang, context, **kwargs):
        captured.append((size.height(), kwargs['header_bottom_mm'], depth_range))
        return original(painter, form, size, source, depth_range, columns, lang, context, **kwargs)
    monkeypatch.setattr(masterlog_renderer, '_paint_columns', capture)
    target = tmp_path / 'controlled.pdf'
    export_masterlog_pdf(template, session, target, settings=settings)
    points_per_mm = 72 / 25.4
    with fitz.open(target) as document:
        assert document.page_count == len(captured)
        assert document.page_count >= (1 if page_format == 'roll' else 2)
        for index, page in enumerate(document):
            text = page.get_text()
            for value in ('DOC-42', 'Approved', 'Engineer A', 'Engineer B', 'Engineer C', '145 — 355 m'):
                assert value in text
            assert 'Vendor date' not in text and 'Acquisition date' not in text and 'STALE RANGE' not in text
            assert (hydrocarbon_report_labels(language).report_date in text) == bool(date)
            if date:
                assert date in text
            bottom, header_bottom, interval = captured[index]
            assert (bottom - header_bottom - masterlog_renderer._masterlog_column_heading_height(template)) == pytest.approx(
                (interval[1] - interval[0]) * 1000 / masterlog_renderer._depth_scale(template), abs=0.15)
            for rect in page.search_for('Engineer C'):
                assert rect.y0 >= template.header_height_mm * points_per_mm
                assert rect.y1 <= header_bottom * points_per_mm
            assert bottom * points_per_mm <= page.rect.height - 10 * points_per_mm + 0.5
    assert template == before
    np.testing.assert_array_equal(original_depth, session.current_dataset.depth)
    np.testing.assert_array_equal(original_curve, session.current_dataset.curves[curve_id].values)


def test_control_layout_language_independent_and_legacy_inactive(qapp):
    session, template = controlled_form()
    session.current_well.passport = WellPassport(texts_i18n={'header.field': {'ru': '', 'kk': 'Кен орны', 'en': ''}})
    layouts = [masterlog_document_control_layout(template, session, (145, 355), 210, language) for language in AppLanguage]
    assert len({layout.height_mm for layout in layouts}) == 1
    ranges = [masterlog_page_ranges(template, session, MasterlogOutputSettings(145, 355, language)) for language in AppLanguage]
    assert ranges[0] == ranges[1] == ranges[2]
    template.properties['header_fields'] = {'header.interval': 'legacy interval'}
    assert masterlog_document_control_layout(template, session, (145, 355), 210) is None


@pytest.mark.parametrize('dpi', [72, 96, 144, 300, 600])
@pytest.mark.parametrize('width', [25, 200])
def test_controlled_long_text_remains_outside_plot(qapp, monkeypatch, dpi, width):
    session, template = controlled_form('2026-09-30')
    template.page_format = 'roll'
    template.columns = [MasterlogColumnTemplate('depth', 'Depth', 'depth', width)]
    for field in ('header.document_number', 'header.confidentiality', 'header.prepared_by'):
        template.properties['header_fields'][field] = 'Very long metadata ' * 200
    size = masterlog_size_mm(template, session, depth_range=(145, 355))
    image = QImage(round(size.width() * dpi / 25.4), round(size.height() * dpi / 25.4), QImage.Format.Format_ARGB32)
    image.setDotsPerMeterX(round(dpi / 0.0254))
    image.setDotsPerMeterY(round(dpi / 0.0254))
    painter = QPainter(image)
    regions = []
    original_draw = masterlog_renderer._draw_control_text
    def capture(painter, rect, text, **kwargs):
        regions.append(QRectF(rect))
        return original_draw(painter, rect, text, **kwargs)
    monkeypatch.setattr(masterlog_renderer, '_draw_control_text', capture)
    try:
        paint_masterlog(painter, QRectF(image.rect()), template, session, depth_range=(145, 355), page_label='Page 1 of 1')
    finally:
        painter.end()
    layout = masterlog_document_control_layout(template, session, (145, 355), width)
    graph_top = template.header_height_mm + layout.height_mm
    footer_top = size.height() - layout.footer_height_mm
    for rect in regions:
        assert rect.x() >= 0 and rect.right() <= width
        assert rect.bottom() <= graph_top or rect.top() >= footer_top
