from copy import deepcopy
from unittest.mock import MagicMock

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, MasterlogColumnTemplate, MasterlogCurveStyle, MasterlogTemplate
from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


def _dataset():
    dataset = Dataset('log', 'Log', DatasetKind.GTI, DepthDomain.MD, np.array([100., 101., 102.]))
    curve = dataset.upsert_curve('VENDOR', np.array([1., 2., 3.]), unit='ppm')
    return dataset, {'TG': curve.metadata.curve_id}


@pytest.mark.parametrize('line_style,pen_style', [('solid', Qt.PenStyle.SolidLine), ('dash', Qt.PenStyle.DashLine),
                                                 ('dot', Qt.PenStyle.DotLine), ('dash_dot', Qt.PenStyle.DashDotLine)])
@pytest.mark.parametrize('line_width', [0.8, 10.0])
def test_legend_line_key_matches_actual_curve_style_and_bound_unit(qapp, line_style, pen_style, line_width):
    dataset, bindings = _dataset()
    column = MasterlogColumnTemplate('gas', 'Gas', 'curves', 50, ['TG'], show_legend=True,
                                    curve_styles={'TG': MasterlogCurveStyle('#111111', line_width, line_style)})
    before = deepcopy(column)
    painter = MagicMock()
    renderer._paint_column_heading(painter, QRectF(0, 0, 50, 12), column, dataset, bindings)
    painter.drawLine.assert_called_once()
    key_pen = next(c.args[0] for c in painter.setPen.call_args_list if hasattr(c.args[0], 'widthF'))
    assert key_pen.style() == pen_style
    assert key_pen.widthF() == line_width
    assert key_pen.color().name() == '#111111'
    label_rect, _, text = painter.drawText.call_args.args
    assert text == 'TG 1–3 (ppm)'
    line = painter.drawLine.call_args.args[0]
    assert line.x2() < label_rect.left()
    assert painter.setClipRect.call_args.args[0].right() < label_rect.left()
    assert label_rect.width() > 0
    actual = MagicMock()
    renderer._paint_curve_column(actual, QRectF(0, 0, 50, 100), column, dataset, (100, 102), bindings)
    actual.drawPath.assert_called_once()
    actual_pen = next(c.args[0] for c in actual.setPen.call_args_list if hasattr(c.args[0], 'widthF'))
    assert actual_pen == key_pen
    assert column == before


def test_point_key_and_curve_share_the_same_source_identifiers(qapp, monkeypatch):
    dataset, bindings = _dataset()
    identifiers = []
    def point_presentation(values):
        identifiers.append(tuple(values))
        return True
    monkeypatch.setattr(renderer, 'uses_gas_point_presentation', point_presentation)
    column = MasterlogColumnTemplate('gas', 'Gas', 'curves', 50, ['TG'], show_legend=True)
    painter = MagicMock()
    renderer._paint_column_heading(painter, QRectF(0, 0, 50, 12), column, dataset, bindings)
    assert painter.drawEllipse.call_count == 3
    painter.drawLine.assert_not_called()
    plot = MagicMock()
    renderer._paint_curve_column(plot, QRectF(0, 0, 50, 100), column, dataset, (100, 102), bindings)
    assert plot.drawEllipse.call_count == 3
    plot.drawPath.assert_not_called()
    assert identifiers[0] == identifiers[1]
    label_rect = painter.drawText.call_args.args[0]
    for call in painter.drawEllipse.call_args_list:
        assert call.args[0].right() < label_rect.left()


@pytest.mark.parametrize('width', [1.0, 20.0, 100.0])
def test_missing_curve_has_no_fabricated_key_or_unit_and_narrow_cells_are_bounded(qapp, width):
    dataset, bindings = _dataset()
    column = MasterlogColumnTemplate('gas', 'Gas', 'curves', width, ['TG', 'MISSING'], show_legend=True)
    painter = MagicMock()
    renderer._paint_column_heading(painter, QRectF(0, 0, width, 12), column, dataset, bindings)
    painter.drawLine.assert_called_once()
    for call in painter.drawText.call_args_list:
        assert call.args[0].width() > 0
        assert call.args[0].left() >= 0
        assert call.args[0].right() <= width
    assert painter.drawText.call_args.args[2] == 'MISSING'


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('page_format', ['A4', 'A3', 'roll'])
def test_legend_keys_units_and_ranges_render_after_project_reopen(qapp, tmp_path, language, page_format):
    dataset, bindings = _dataset()
    session = ProjectSession()
    session.add_dataset(dataset, 'Well')
    column = MasterlogColumnTemplate('gas', 'Gas', 'curves', 60, ['TG'], show_legend=True,
                                    curve_styles={'TG': MasterlogCurveStyle('#111111', 0.8, 'dash_dot')})
    template = MasterlogTemplate('form', 'Form', page_format=page_format, columns=[column],
                                properties={'dataset_curve_bindings': {'log': bindings}})
    session.project.masterlog_templates['form'] = template
    package = tmp_path / 'legend.geologpkg'
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates['form']
    before = deepcopy(saved)
    values = restored.current_dataset.curve_by_mnemonic('VENDOR').values.copy()
    pdf = tmp_path / 'legend.pdf'
    renderer.export_masterlog_pdf(saved, restored, pdf, settings=MasterlogOutputSettings(100, 102, language))
    with fitz.open(pdf) as document:
        assert len(document) >= 1
        assert any(d['dashes'] != '[] 0' for d in document[0].get_drawings() if d['color'])
    image = QImage(600, 150, QImage.Format.Format_ARGB32)
    image.fill('white')
    painter = QPainter(image)
    painter.scale(10, 10)
    try:
        renderer._paint_column_heading(painter, QRectF(0, 0, 60, 12), saved.columns[0], restored.current_dataset, bindings)
    finally:
        painter.end()
    assert any(image.pixelColor(x, y).lightness() < 100
               for x in range(5, 65) for y in range(77, 85))
    assert saved == before
    np.testing.assert_array_equal(restored.current_dataset.curve_by_mnemonic('VENDOR').values, values)
