import base64
from copy import deepcopy
from dataclasses import replace
from io import BytesIO

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetricsF, QImage, QPainter

from geoworkbench.printing import hydrocarbon_interpretation_chart as chart
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_charts import _session_with_report_curves


def _profile(kind):
    visual = chart.modern_oilfield_report_profile()
    if kind == "custom":
        return replace(visual, typography=replace(visual.typography, title_pt=30, footer_pt=15),
                       palette=replace(visual.palette, text="#563410", text_secondary="#205432"))
    if kind == "large":
        return replace(visual, typography=replace(visual.typography, title_pt=36, footer_pt=36))
    return visual


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
@pytest.mark.parametrize("role", ["title", "footer"])
def test_preview_text_fits_complete_localized_label_and_restores_painter(qapp, language, kind, role):
    visual = _profile(kind)
    text = chart._labels(language)[role]
    rect = QRectF(10, 10, 1820, 45 if role == "title" else 84)
    flags = (Qt.AlignmentFlag.AlignCenter if role == "title" else
             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)
    records = []

    class RecordingPainter(QPainter):
        def drawText(self, actual_rect, actual_flags, actual_text):
            records.append((self.font(), self.pen().color().name(), actual_text))
            bounds = QFontMetricsF(self.font(), self.device()).boundingRect(
                QRectF(0, 0, actual_rect.width(), 10000), actual_flags, actual_text)
            assert bounds.width() <= actual_rect.width()
            assert bounds.height() <= actual_rect.height()
            return super().drawText(actual_rect, actual_flags, actual_text)

    image = QImage(1840, 110, QImage.Format.Format_ARGB32)
    image.fill("white")
    painter = RecordingPainter(image)
    state = (painter.font(), painter.pen(), painter.transform())
    size = visual.typography.title_pt if role == "title" else visual.typography.footer_pt
    color = visual.palette.text if role == "title" else visual.palette.text_secondary
    try:
        chart._paint_preview_text(painter, rect, text, size, color, flags, bold=role == "title")
        assert (painter.font(), painter.pen(), painter.transform()) == state
    finally:
        painter.end()
    assert len(records) == 1
    assert records[0][2] == text
    assert records[0][1] == color.lower()
    assert records[0][0].bold() == (role == "title")
    assert 1 <= records[0][0].pointSizeF() <= size
    if kind == "default":
        assert records[0][0].pointSizeF() == size
    assert any(image.pixelColor(x, y).lightness() < 200
               for y in range(10, int(rect.bottom())) for x in range(10, 1830))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
def test_production_preview_after_reopen_uses_profile_and_preserves_source(qapp, tmp_path, monkeypatch, language, kind):
    visual = _profile(kind)
    monkeypatch.setattr(chart, "modern_oilfield_report_profile", lambda: visual)
    controller = ProjectController(session=_session_with_report_curves())
    path = tmp_path / "project.geoproj"
    controller.save_project(path)
    restored = ProjectController().open_project(path)
    report = build_hydrocarbon_interpretation_report(restored)
    before = deepcopy(report)
    dataset = restored.current_dataset
    arrays = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    calls = []
    original = chart._paint_preview_text

    def capture(painter, rect, text, size, color, flags, **kwargs):
        calls.append((text, size, color, QRectF(rect)))
        return original(painter, rect, text, size, color, flags, **kwargs)

    monkeypatch.setattr(chart, "_paint_preview_text", capture)
    uri = chart.hydrocarbon_interpretation_chart_data_uri(report, dataset, language)
    with Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as image:
        assert image.width == 2000
        assert image.height >= 1280
        assert image.convert("L").getextrema()[0] < 200
    labels = chart._labels(language)
    axis = [(labels["depth"] + ", m", visual.typography.section_pt, visual.palette.text)] + [
        (f"{1300 + index * 12:.1f}", visual.typography.table_pt, visual.palette.text)
        for index in range(11)
    ]
    legend = [(f"{spec.code} {spec.label(language)}", visual.typography.caption_pt, visual.palette.text)
              for spec in chart.fluid_marker_legend_specs([item.fluid_hypothesis for item in report.candidates])]
    assert [(text, size, color) for text, size, color, rect in calls] == [
        (labels["title"], visual.typography.title_pt, visual.palette.text),
        *axis, *axis,
        *legend,
        (labels["footer"], visual.typography.footer_pt, visual.palette.text_secondary),
    ]
    assert calls[0][3] == QRectF(90, 18, 1820, 45)
    assert calls[-1][3].width() == 1820 and calls[-1][3].height() == 84
    assert report.candidates == before.candidates
    assert report.gas_context_events == before.gas_context_events
    for key, values in arrays.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
