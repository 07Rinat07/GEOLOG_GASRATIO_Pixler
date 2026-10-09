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
from geoworkbench.printing.hydrocarbon_fluid_markers import all_fluid_marker_specs
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_charts import _session_with_report_curves


def _profile(kind):
    visual = chart.modern_oilfield_report_profile()
    if kind == "default":
        return visual
    return replace(visual, typography=replace(visual.typography, caption_pt=16 if kind == "custom" else 36),
                   palette=replace(visual.palette, text="#563410"))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
@pytest.mark.parametrize("width", [600, 1820])
def test_fluid_legend_preserves_all_phase_keys_and_fits_full_labels(qapp, monkeypatch, language, kind, width):
    visual = _profile(kind)
    monkeypatch.setattr(chart, "modern_oilfield_report_profile", lambda: visual)
    hypotheses = ["probable_gas", "gas_condensate_or_high_api_oil", "light_oil_high_gor",
                  "probable_liquid_hydrocarbons", "indeterminate"]
    candidates = tuple(SimpleNamespace(fluid_hypothesis=value) for value in hypotheses)
    before = deepcopy(candidates)
    texts, markers, requests = [], [], []
    original_marker, original_font = chart.draw_fluid_marker, chart.print_font

    def marker(painter, center, spec, **kwargs):
        markers.append((center.x(), center.y(), spec, kwargs))
        return original_marker(painter, center, spec, **kwargs)

    def font(size, **kwargs):
        requests.append((size, kwargs["text"]))
        return original_font(size, **kwargs)

    monkeypatch.setattr(chart, "draw_fluid_marker", marker)
    monkeypatch.setattr(chart, "print_font", font)

    class RecordingPainter(QPainter):
        def drawText(self, rect, flags, text):
            bounds = QFontMetricsF(self.font(), self.device()).boundingRect(
                QRectF(0, 0, rect.width(), 10000), flags, text)
            assert bounds.width() <= rect.width() and bounds.height() <= rect.height()
            texts.append((text, self.pen().color().name(), QRectF(rect)))
            return super().drawText(rect, flags, text)

    image = QImage(width + 40, 70, QImage.Format.Format_ARGB32)
    image.fill("white")
    painter = RecordingPainter(image)
    try:
        chart._draw_whole_well_fluid_legend(painter, QRectF(20, 20, width, 30), candidates, language)
    finally:
        painter.end()
    specs = all_fluid_marker_specs()
    assert [text for text, color, rect in texts] == [f"{spec.code} {spec.label(language)}" for spec in specs]
    assert all(color == visual.palette.text for text, color, rect in texts)
    for index, (x, y, spec, kwargs) in enumerate(markers):
        assert spec == specs[index]
        assert x == pytest.approx(27 + index * width / 5)
        assert y == 35 and kwargs == {"size": 7.0}
        assert texts[index][2] == QRectF(34 + index * width / 5, 28, width / 5 - 16, 14)
        assert (visual.typography.caption_pt, texts[index][0]) in requests
    assert candidates == before


@pytest.mark.parametrize("language", list(AppLanguage))
def test_empty_fluid_legend_draws_nothing(qapp, monkeypatch, language):
    def unexpected(*args, **kwargs):
        pytest.fail("empty legend must not draw markers or text")
    monkeypatch.setattr(chart, "draw_fluid_marker", unexpected)
    monkeypatch.setattr(chart, "_paint_preview_text", unexpected)
    image = QImage(100, 50, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    try:
        chart._draw_whole_well_fluid_legend(painter, QRectF(0, 0, 100, 50), (), language)
    finally:
        painter.end()


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
def test_production_fluid_legend_after_reopen_preserves_data(qapp, tmp_path, monkeypatch, language, kind):
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
    expected = [f"{spec.code} {spec.label(language)}" for spec in
                chart.fluid_marker_legend_specs([item.fluid_hypothesis for item in report.candidates])]
    assert expected
    calls = []
    original = chart._paint_preview_text

    def capture(painter, rect, text, size, color, flags, **kwargs):
        if text in expected:
            calls.append((text, size, color))
        return original(painter, rect, text, size, color, flags, **kwargs)

    monkeypatch.setattr(chart, "_paint_preview_text", capture)
    uri = chart.hydrocarbon_interpretation_chart_data_uri(report, dataset, language)
    with Image.open(BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as image:
        assert image.width == 2000 and image.height >= 1280
    assert calls == [(text, visual.typography.caption_pt, visual.palette.text) for text in expected]
    assert report.candidates == before.candidates
    assert report.gas_context_events == before.gas_context_events
    for key, values in arrays.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
