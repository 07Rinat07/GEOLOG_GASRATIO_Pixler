import base64
from copy import deepcopy
from dataclasses import replace
from io import BytesIO

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFontMetricsF, QImage, QPainter

from geoworkbench.printing import hydrocarbon_interpretation_chart as chart
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_charts import _session_with_report_curves


def _profile(kind):
    visual = chart.modern_oilfield_report_profile()
    if kind == "default":
        return visual
    size = 18 if kind == "custom" else 36
    return replace(visual, typography=replace(visual.typography, section_pt=size, table_pt=size),
                   palette=replace(visual.palette, text="#563410", text_muted="#205432",
                                   border="#315872", border_strong="#612345", table_alt="#eff4e8"))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
@pytest.mark.parametrize("limits", [(-120, -20), (1300, 1420), (-1234567, 7654321)])
def test_depth_axis_preserves_signed_values_ticks_and_fits_profile(qapp, monkeypatch, language, side, kind, limits):
    visual = _profile(kind)
    monkeypatch.setattr(chart, "modern_oilfield_report_profile", lambda: visual)
    texts, lines, frames, fills = [], [], [], []

    class RecordingPainter(QPainter):
        def drawText(self, rect, flags, text):
            bounds = QFontMetricsF(self.font(), self.device()).boundingRect(
                QRectF(0, 0, rect.width(), 10000), int(flags), text)
            assert bounds.width() <= rect.width()
            assert bounds.height() <= rect.height()
            texts.append((text, self.font(), self.pen().color().name(), QRectF(rect)))
            return super().drawText(rect, flags, text)

        def drawLine(self, line):
            lines.append((line.x1(), line.y1(), line.x2(), line.y2(), self.pen().color().name()))
            return super().drawLine(line)

        def drawRect(self, rect):
            frames.append((QRectF(rect), self.pen().color().name()))
            return super().drawRect(rect)

        def fillRect(self, rect, color):
            fills.append((QRectF(rect), color.name()))
            return super().fillRect(rect, color)

    image = QImage(180, 500, QImage.Format.Format_ARGB32)
    image.fill("white")
    painter = RecordingPainter(image)
    rect = QRectF(20, 60, 128, 400)
    try:
        chart._draw_depth_axis(painter, rect, *limits, "m", side=side, language=language)
    finally:
        painter.end()
    assert texts[0][0] == chart._labels(language)["depth"] + ", m"
    assert texts[0][1].bold()
    assert texts[0][1].pointSizeF() <= visual.typography.section_pt
    assert [item[0] for item in texts[1:]] == [
        f"{limits[0] + index / 10 * (limits[1] - limits[0]):.1f}" for index in range(11)]
    assert all(not font.bold() and font.pointSizeF() <= visual.typography.table_pt
               for text, font, color, box in texts[1:])
    assert all(color == visual.palette.text for text, font, color, box in texts)
    assert fills == [(rect, visual.palette.table_alt)]
    assert frames == [(rect, visual.palette.border_strong)] * 2
    assert len(lines) == 51
    major_lines = [line for line in lines if line[4] == visual.palette.text_muted]
    minor_lines = [line for line in lines if line[4] == visual.palette.border]
    assert len(major_lines) == 11 and len(minor_lines) == 40
    assert [line[1] for line in major_lines] == [60 + index * 40 for index in range(11)]
    for x1, y1, x2, y2, color in lines:
        assert y1 == y2 and 60 <= y1 <= 460
        length = 12 if color == visual.palette.text_muted else 6
        assert (x1, x2) == ((148 - length, 148) if side == "left" else (20, 20 + length))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
def test_production_depth_preview_after_reopen_keeps_source(qapp, tmp_path, monkeypatch, language, kind):
    visual = _profile(kind)
    monkeypatch.setattr(chart, "modern_oilfield_report_profile", lambda: visual)
    controller = ProjectController(session=_session_with_report_curves(depth_start=-120, depth_span=100))
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
        calls.append((text, size, color))
        return original(painter, rect, text, size, color, flags, **kwargs)

    monkeypatch.setattr(chart, "_paint_preview_text", capture)
    uri = chart.hydrocarbon_interpretation_chart_data_uri(report, dataset, language)
    with Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as image:
        assert image.width == 2000 and image.height >= 1280
    numeric = [(text, size, color) for text, size, color in calls if text.startswith("-")]
    assert len(numeric) == 22
    assert all(size == visual.typography.table_pt and color == visual.palette.text
               for text, size, color in numeric)
    assert report.candidates == before.candidates
    assert report.gas_context_events == before.gas_context_events
    for key, values in arrays.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
