import base64
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace

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
    return replace(visual, typography=replace(visual.typography, section_pt=size, table_pt=size,
                                              body_pt=size, caption_pt=size),
                   palette=replace(visual.palette, page="#f4efe7", text="#563410", text_muted="#205432",
                                   border="#315872", border_strong="#612345"))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
@pytest.mark.parametrize("path", ["panel", "geology", "badge"])
def test_complete_preview_profile_fits_panels_empty_geology_and_codes(qapp, monkeypatch, language, kind, path):
    visual = _profile(kind)
    monkeypatch.setattr(chart, "modern_oilfield_report_profile", lambda: visual)
    records, requests, fills, lines = [], [], [], []
    original = chart._paint_preview_text

    def capture(painter, rect, text, size, color, flags, **kwargs):
        requests.append((text, size, color, kwargs.get("bold", False)))
        return original(painter, rect, text, size, color, flags, **kwargs)

    monkeypatch.setattr(chart, "_paint_preview_text", capture)

    class RecordingPainter(QPainter):
        def drawText(self, rect, flags, text):
            bounds = QFontMetricsF(self.font(), self.device()).boundingRect(
                QRectF(0, 0, rect.width(), 10000), int(flags), text)
            assert bounds.width() <= rect.width() and bounds.height() <= rect.height()
            records.append(text)
            return super().drawText(rect, flags, text)

        def fillRect(self, rect, color):
            fills.append(color.name())
            return super().fillRect(rect, color)

        def drawLine(self, line):
            lines.append(self.pen().color().name())
            return super().drawLine(line)

    image = QImage(600, 500, QImage.Format.Format_ARGB32)
    image.fill("white")
    painter = RecordingPainter(image)
    rect = QRectF(30, 100, 400, 300)
    depth = np.linspace(0, 10, 11)
    try:
        if path == "panel":
            chart._draw_panel(painter, rect, depth, np.isfinite(depth), 0, 10,
                              "total", (), (), language, {})
        elif path == "geology":
            chart._draw_geology_preview_tracks(painter, (rect, rect.translated(140, 0)), None,
                                               ("cuttings", "lba"), ("cuttings", "lba"), 0, 10, language)
        else:
            candidate = SimpleNamespace(top_depth=2, bottom_depth=4, fluid_hypothesis="probable_gas")
            chart._draw_whole_well_fluid_markers(painter, rect, 0, 10, (candidate,))
    finally:
        painter.end()
    assert records == [text for text, size, color, bold in requests]
    assert requests
    if path == "panel":
        assert requests == [(str(index * 25), visual.typography.caption_pt, visual.palette.text_muted, False)
                            for index in range(5)] + [
            (chart._labels(language)["total"], visual.typography.section_pt, visual.palette.text, True)]
        assert fills == [visual.palette.page]
        assert len(lines) == 56
        assert set(lines) == {visual.palette.border, visual.palette.border_strong}
    elif path == "geology":
        assert len(requests) == 4
        assert requests[0][1:] == (visual.typography.table_pt, visual.palette.text, True)
        assert requests[1][1:] == (visual.typography.body_pt, visual.palette.text_muted, False)
        assert requests[2][1:] == requests[0][1:] and requests[3][1:] == requests[1][1:]
        assert fills == [visual.palette.page] * 2
        assert len(lines) == 22 and set(lines) == {visual.palette.border}
    else:
        assert requests == [("G", visual.typography.caption_pt, visual.palette.text, True)]
        assert fills == [visual.palette.page]


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
def test_whole_preview_profile_after_reopen_keeps_measurements(qapp, tmp_path, monkeypatch, language, kind):
    visual = _profile(kind)
    monkeypatch.setattr(chart, "modern_oilfield_report_profile", lambda: visual)
    controller = ProjectController(session=_session_with_report_curves())
    target = tmp_path / "project.geoproj"
    controller.save_project(target)
    restored = ProjectController().open_project(target)
    dataset = restored.current_dataset
    arrays = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    report = build_hydrocarbon_interpretation_report(restored)
    before = deepcopy(report)
    calls = []
    original = chart._paint_preview_text

    def capture(painter, rect, text, size, color, flags, **kwargs):
        calls.append((text, size, color))
        return original(painter, rect, text, size, color, flags, **kwargs)

    monkeypatch.setattr(chart, "_paint_preview_text", capture)
    uri = chart.hydrocarbon_interpretation_chart_data_uri(report, dataset, language)
    with Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as image:
        assert image.width == 2000 and image.height >= 1280
        assert image.convert("RGB").getpixel((0, 0)) == tuple(bytes.fromhex(visual.palette.page[1:]))
    assert len(calls) > 30
    assert any(size == visual.typography.section_pt for text, size, color in calls)
    assert any(size == visual.typography.table_pt for text, size, color in calls)
    assert any(size == visual.typography.caption_pt for text, size, color in calls)
    assert report.candidates == before.candidates and report.gas_context_events == before.gas_context_events
    for key, values in arrays.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
