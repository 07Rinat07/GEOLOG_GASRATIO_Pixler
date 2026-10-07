from copy import deepcopy
from dataclasses import replace
from unittest.mock import MagicMock

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, MasterlogColumnTemplate, MasterlogTemplate
from geoworkbench.printing import masterlog_renderer as renderer
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


@pytest.mark.parametrize('grayscale', [False, True])
@pytest.mark.parametrize('alpha', [0.0, 0.6, 1.0])
def test_grid_uses_profile_with_saved_alpha_and_unchanged_geometry(qapp, monkeypatch, grayscale, alpha):
    profile = modern_oilfield_report_profile(grayscale=grayscale)
    profile = replace(profile, layout=replace(profile.layout, thin_rule_pt=1.2))
    monkeypatch.setattr(renderer, 'modern_oilfield_report_profile', lambda: profile)
    column = MasterlogColumnTemplate('depth', 'Depth', 'depth', 25, grid_x=True, grid_y=True, grid_print=True, grid_major_divisions=2,
                                    grid_minor_divisions=2, grid_alpha=alpha)
    before = deepcopy(column)
    painter = MagicMock()
    renderer._paint_column_grid(painter, QRectF(0, 0, 40, 100), column, (100, 110))
    pens = [c.args[0] for c in painter.setPen.call_args_list]
    major = [p for p in pens if p.color().name() == profile.palette.border_strong]
    minor = [p for p in pens if p.color().name() == profile.palette.border]
    assert major and minor
    for pen in major:
        assert pen.widthF() == pytest.approx(1.2 * 25.4 / 72)
        assert pen.color().alphaF() == pytest.approx(alpha, abs=0.0001)
    for pen in minor:
        assert pen.widthF() == pytest.approx(0.6 * 25.4 / 72)
        assert pen.color().alphaF() == pytest.approx(alpha * 0.45, abs=0.0001)
    horizontal = [c.args[0] for c in painter.drawLine.call_args_list if c.args[0].y1() == c.args[0].y2()]
    assert {line.y1() for line in horizontal} >= {0, 50, 100}
    assert column == before
    painter.reset_mock()
    column.grid_print = False
    renderer._paint_column_grid(painter, QRectF(0, 0, 40, 100), column, (100, 110))
    painter.drawLine.assert_not_called()


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('dpi', [72, 300, 600])
def test_pdf_grid_and_depth_axis_follow_profile_after_reopen(qapp, tmp_path, monkeypatch, language, dpi):
    session = ProjectSession()
    dataset = Dataset('log', 'Log', DatasetKind.GTI, DepthDomain.MD, np.array([100., 105., 110.]))
    session.add_dataset(dataset, 'Well')
    column = MasterlogColumnTemplate('depth', 'Depth', 'depth', 25, grid_x=True, grid_y=True, grid_print=True, grid_alpha=1.0)
    template = MasterlogTemplate('form', 'Form', columns=[column])
    session.project.masterlog_templates['form'] = template
    package = tmp_path / 'grid.geologpkg'
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    saved = restored.project.masterlog_templates['form']
    before = deepcopy(saved)
    depth = restored.current_dataset.depth.copy()
    profile = modern_oilfield_report_profile(grayscale=True)
    profile = replace(profile, typography=replace(profile.typography, table_pt=9),
                      layout=replace(profile.layout, thin_rule_pt=1.1))
    monkeypatch.setattr(renderer, 'modern_oilfield_report_profile', lambda: profile)
    sizes = []
    original = renderer._set_scaled_font_points
    def record_size(painter, font, points):
        sizes.append(points)
        original(painter, font, points)
    monkeypatch.setattr(renderer, '_set_scaled_font_points', record_size)
    original_writer = renderer.QPdfWriter
    class ResolutionWriter(original_writer):
        def setResolution(self, requested):
            super().setResolution(dpi)
    monkeypatch.setattr(renderer, 'QPdfWriter', ResolutionWriter)
    target = tmp_path / 'grid.pdf'
    renderer.export_masterlog_pdf(saved, restored, target, settings=MasterlogOutputSettings(100, 110, language))
    assert 9 in sizes
    with fitz.open(target) as document:
        assert len(document) >= 1
        rgb = tuple(int(profile.palette.border_strong[i:i+2], 16)/255 for i in (1, 3, 5))
        drawings = [d for d in document[0].get_drawings() if d['color'] and
                    all(abs(a-b) < 0.002 for a, b in zip(d['color'], rgb, strict=True))]
        assert drawings
        assert any(d['width'] == pytest.approx(1.1, abs=0.03) for d in drawings)
    assert saved == before
    np.testing.assert_array_equal(restored.current_dataset.depth, depth)
