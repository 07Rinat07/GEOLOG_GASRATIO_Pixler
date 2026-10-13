from copy import deepcopy
from dataclasses import replace

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPageLayout

from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage, chart_geometry
from geoworkbench.printing.hydrocarbon_interpretation_report import export_hydrocarbon_interpretation_pdf
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import default_interpretation_report_identity
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_charts import _session_with_report_curves


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('profile', ['standard', 'opus'])
@pytest.mark.parametrize('orientation', [QPageLayout.Orientation.Portrait, QPageLayout.Orientation.Landscape])
def test_clean_report_keeps_passport_and_source_without_repeated_notes(qapp, tmp_path, language, profile, orientation):
    session = _session_with_report_curves(depth_span=120, samples=241)
    dataset = session.current_dataset
    before = deepcopy(dataset)
    report = replace(build_hydrocarbon_interpretation_report(session), report_profile=profile)
    identity = replace(default_interpretation_report_identity(report, language),
                       document_number='CLIENT-42', document_status='APPROVED', confidentiality='CLIENT ONLY')
    path = export_hydrocarbon_interpretation_pdf(report, tmp_path / 'clean.pdf', language=language,
        dataset=dataset, include_chart=True, identity=identity, orientation=orientation)
    with fitz.open(path) as document:
        assert len(document) >= 3
        assert 'CLIENT-42' in document[0].get_text()
        for page in document:
            text = page.get_text()
            assert all(note not in text for note in ('Обычные многокривые дорожки',
                'Кәдімгі көп қисықты жолдар', 'Ordinary multi-curve tracks'))
            footer = page.get_text(clip=fitz.Rect(0, page.rect.height - 40,
                                                page.rect.width, page.rect.height))
            assert all(value not in footer for value in ('CLIENT-42', 'APPROVED', 'CLIENT ONLY'))
    np.testing.assert_array_equal(dataset.depth, before.depth)
    for key in dataset.curves:
        np.testing.assert_array_equal(dataset.curves[key].values, before.curves[key].values)


def test_removed_note_height_is_available_to_plot_without_stretching_depth_scale():
    rect = QRectF(0, 0, 510, 740)
    page = DepthPage(1000, 1200, 500, 1000)
    with_note = chart_geometry(rect, page, 3, chart_note_height=48)
    clean = chart_geometry(rect, page, 3, chart_note_height=0)
    assert clean.left_axis_rect.height() == pytest.approx(with_note.left_axis_rect.height() + 48)
    assert clean.note_rect.height() == 0
    assert clean.legend_rect.bottom() <= rect.bottom()
