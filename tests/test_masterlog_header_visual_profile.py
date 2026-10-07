from copy import deepcopy
from dataclasses import replace

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, MasterlogHeaderElement, MasterlogTemplate
from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.lithology_legend import LithologyLegendEntry


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('grayscale', [False, True])
def test_header_defaults_follow_profile_and_saved_overrides_win(qapp, monkeypatch, language, grayscale):
    profile = modern_oilfield_report_profile(grayscale=grayscale)
    profile = replace(profile, typography=replace(profile.typography, body_pt=11, table_pt=9, caption_pt=8),
                      layout=replace(profile.layout, strong_rule_pt=1.8, thin_rule_pt=0.9))
    monkeypatch.setattr(renderer, 'modern_oilfield_report_profile', lambda: profile)
    image = QImage(600, 300, QImage.Format.Format_ARGB32)
    image.fill(QColor('white'))
    painter = QPainter(image)
    painter.scale(3, 3)
    template = MasterlogTemplate('form', 'Form')
    session = ProjectSession()
    sizes = []
    original_font = renderer._set_scaled_font_mm
    def record_font(painter, font, size):
        sizes.append(size)
        original_font(painter, font, size)
    monkeypatch.setattr(renderer, '_set_scaled_font_mm', record_font)
    try:
        line = MasterlogHeaderElement('line', 'line', 1, 1, 100, 0, {})
        renderer._paint_header_element(painter, line, session, template, None, language, {})
        assert painter.pen().color().name() == profile.palette.border_strong
        assert painter.pen().widthF() == pytest.approx(1.8 * 25.4 / 72)
        line.properties = {'color': '#123456', 'width': 0.8}
        renderer._paint_header_element(painter, line, session, template, None, language, {})
        assert painter.pen().color().name() == '#123456'
        assert painter.pen().widthF() == pytest.approx(0.8)
        text = MasterlogHeaderElement('text', 'text', 2, 5, 100, 10, {'text': 'RU Қазақша EN'})
        renderer._paint_header_element(painter, text, session, template, None, language, {})
        assert painter.pen().color().name() == profile.palette.text
        assert sizes[-1] == pytest.approx(11 * 25.4 / 72)
        text.properties.update({'color': '#654321', 'font_size_mm': 4.2})
        renderer._paint_header_element(painter, text, session, template, None, language, {})
        assert painter.pen().color().name() == '#654321'
        assert sizes[-1] == 4.2
        renderer._paint_image_placeholder(painter, QRectF(2, 30, 100, 20), {}, language)
        assert sizes[-1] == pytest.approx(8 * 25.4 / 72)
        assert image.pixelColor(12, 96).name() == profile.palette.accent_soft
        renderer._paint_image_placeholder(painter, QRectF(2, 55, 100, 20),
                                         {'background': '#abcdef', 'placeholder_font_size_mm': 3.1}, language)
        assert image.pixelColor(12, 171).name() == '#abcdef'
        assert sizes[-1] == 3.1
        renderer._paint_lba_legend(painter, QRectF(110, 5, 80, 80), {}, language)
        assert sizes[-1] == pytest.approx(9 * 25.4 / 72)
        entry = LithologyLegendEntry('sand', 'S', 'Sand Қазақша', '#ffcc00', 'solid')
        renderer._paint_lithology_legend(painter, QRectF(2, 80, 100, 15), (entry,), {}, language)
        assert sizes[-1] == pytest.approx(9 * 25.4 / 72)
        assert entry.color == '#ffcc00'
        renderer._paint_lba_legend(painter, QRectF(110, 5, 80, 80), {'font_size_mm': 1.9}, language)
        assert sizes[-1] == 1.9
    finally:
        painter.end()


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('page_format', ['A4', 'A3', 'roll'])
def test_masterlog_pdf_and_reusable_header_use_profile_after_reopen(qapp, tmp_path, monkeypatch, language, page_format):
    session = ProjectSession()
    dataset = Dataset('log', 'Log', DatasetKind.GTI, DepthDomain.MD, np.array([100., 101.]))
    dataset.upsert_curve('TG', np.array([1., 2.]), unit='ppm')
    session.add_dataset(dataset, 'Well')
    template = MasterlogTemplate('form', 'Form', page_format=page_format, header_height_mm=40,
                                header_elements=[MasterlogHeaderElement('title', 'text', 5, 5, 100, 10,
                                                                         {'text': 'RU Қазақша EN', 'color': '#123456', 'font_size_mm': 4.0})])
    session.project.masterlog_templates[template.template_id] = template
    package = tmp_path / 'form.geologpkg'
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates['form']
    before = deepcopy(saved)
    values = restored.current_dataset.curve_by_mnemonic('TG').values.copy()
    profile = modern_oilfield_report_profile(grayscale=True)
    profile = replace(profile, palette=replace(profile.palette, page='#eeeeee', border_strong='#444444'))
    monkeypatch.setattr(renderer, 'modern_oilfield_report_profile', lambda: profile)
    output = tmp_path / 'form.pdf'
    renderer.export_masterlog_pdf(saved, restored, output, settings=MasterlogOutputSettings(100, 101, language))
    with fitz.open(output) as document:
        assert len(document) >= 1
        drawings = document[0].get_drawings()
        assert any(d['fill'] and all(abs(v - 238/255) < 0.002 for v in d['fill']) for d in drawings)
        assert any(d['color'] and all(abs(v - 68/255) < 0.002 for v in d['color']) for d in drawings)
    image = QImage(800, 200, QImage.Format.Format_ARGB32)
    image.fill(QColor('white'))
    painter = QPainter(image)
    try:
        renderer.paint_masterlog_header(painter, QRectF(0, 0, 800, 200), saved, restored, language=language)
    finally:
        painter.end()
    assert image.pixelColor(400, 150).name() == '#eeeeee'
    assert saved == before
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic('TG').values, values)
