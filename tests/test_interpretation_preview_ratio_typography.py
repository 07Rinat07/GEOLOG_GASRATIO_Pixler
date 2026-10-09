from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFontMetricsF, QImage, QPainter

from geoworkbench.domain.models import CurveData, CurveMetadata
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
    return replace(visual, typography=replace(visual.typography, table_pt=size, caption_pt=size),
                   palette=replace(visual.palette, text="#563410", text_muted="#205432"))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
@pytest.mark.parametrize("mode", ["haworth", "pixler"])
def test_ratio_preview_labels_fit_full_text_without_changing_scales(qapp, monkeypatch, language, kind, mode):
    visual = _profile(kind)
    monkeypatch.setattr(chart, "modern_oilfield_report_profile", lambda: visual)
    names = ["WH", "BH", "CH"] if mode == "haworth" else [f"PIXLER_C1_C{i}" for i in range(2, 6)]
    depth = np.linspace(0, 10, 11)
    curves = tuple(CurveData(CurveMetadata(name, name, name, "", None, "d"),
                             np.linspace(0.2, 4, 11)) for name in names)
    arrays = [curve.values.copy() for curve in curves]
    texts, requests = [], []
    original = chart._paint_preview_text

    def capture(painter, rect, text, size, color, flags, **kwargs):
        if rect.height() == 13:
            requests.append((text, size, color, QRectF(rect)))
        else:
            assert text == chart._labels(language)["ratios"]
            assert size == visual.typography.section_pt and color == visual.palette.text
        return original(painter, rect, text, size, color, flags, **kwargs)

    monkeypatch.setattr(chart, "_paint_preview_text", capture)

    class RecordingPainter(QPainter):
        def drawText(self, rect, flags, text):
            if rect.height() == 13:
                bounds = QFontMetricsF(self.font(), self.device()).boundingRect(
                    QRectF(0, 0, rect.width(), 10000), int(flags), text)
                assert bounds.width() <= rect.width() and bounds.height() <= rect.height()
                texts.append(text)
            return super().drawText(rect, flags, text)

    image = QImage(500, 450, QImage.Format.Format_ARGB32)
    image.fill("white")
    painter = RecordingPainter(image)
    rect = QRectF(20, 100, 400, 300)
    try:
        assert chart._draw_ratio_preview_tracks(painter, rect, depth, np.isfinite(depth),
                                               0, 10, curves, (), language, header_height=62)
    finally:
        painter.end()
    expected = []
    tracks = chart.ratio_reference_tracks(curves)
    lane_count = max(group for curve, scale, group in tracks) + 1
    for curve, scale, group in tracks:
        name = curve.metadata.canonical_mnemonic.replace("PIXLER_", "").replace("_", "/")
        if chart.ratio_identifier(curve) in {"WH", "BH"}:
            name = {AppLanguage.RU: "Wh (красн.) / Bh (син.)", AppLanguage.KK: "Wh (қызыл) / Bh (көк)",
                    AppLanguage.EN: "Wh (red) / Bh (blue)"}[language]
        ticks = chart.gas_ratio_scale_ticks(scale)
        ticks = ticks if len(ticks) <= 3 else (ticks[0], ticks[len(ticks) // 2], ticks[-1])
        expected.append((name, visual.typography.table_pt, visual.palette.text))
        expected.extend((label, visual.typography.caption_pt, visual.palette.text_muted) for fraction, label in ticks)
    assert [(text, size, color) for text, size, color, box in requests] == expected
    assert texts == [text for text, size, color in expected]
    for text, size, color, box in requests:
        assert box.height() == 13 and 20 <= box.left() < box.right() <= 420
        assert box.top() == (69 if size == visual.typography.table_pt and color == visual.palette.text else 83)
        assert box.width() <= 400 / lane_count
    for curve, values in zip(curves, arrays):
        np.testing.assert_array_equal(curve.values, values)
    np.testing.assert_array_equal(depth, np.linspace(0, 10, 11))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
def test_ratio_profile_reaches_production_preview_after_reopen(qapp, tmp_path, monkeypatch, language, kind):
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
    requests = []
    original = chart._paint_preview_text

    def capture(painter, rect, text, size, color, flags, **kwargs):
        if rect.height() == 13:
            requests.append((text, size, color))
        return original(painter, rect, text, size, color, flags, **kwargs)

    monkeypatch.setattr(chart, "_paint_preview_text", capture)
    assert chart.hydrocarbon_interpretation_chart_data_uri(report, dataset, language).startswith("data:image/png;base64,")
    assert requests
    assert any(size == visual.typography.table_pt and color == visual.palette.text for text, size, color in requests)
    assert any(size == visual.typography.caption_pt and color == visual.palette.text_muted for text, size, color in requests)
    assert report.candidates == before.candidates and report.gas_context_events == before.gas_context_events
    for key, values in arrays.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
