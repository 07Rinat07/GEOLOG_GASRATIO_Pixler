from copy import deepcopy
from dataclasses import replace

import fitz
import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QImage, QPainter, QPdfWriter

from geoworkbench.domain.gas_context_events import GasContextEvent, GasContextEventType
from geoworkbench.printing import gas_context_track as track
from geoworkbench.services.localization import AppLanguage


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("size", [7.6, 12.0])
def test_pdf_context_heading_uses_profile_and_fits_reserved_height(qapp, tmp_path, monkeypatch, language, dpi, size):
    visual = track.modern_oilfield_report_profile()
    monkeypatch.setattr(track, "modern_oilfield_report_profile",
                        lambda: replace(visual, typography=replace(visual.typography, table_pt=size)))
    events = (GasContextEvent("connection", GasContextEventType.CONNECTION_GAS, 0, 10),)
    before = deepcopy(events)
    original = track.paint_track_heading
    calls = []

    def capture(painter, rect, text, font_size, **kwargs):
        calls.append((QRectF(rect), text, font_size, kwargs))
        return original(painter, rect, text, font_size, **kwargs)

    monkeypatch.setattr(track, "paint_track_heading", capture)
    snapshots = []
    for resolution in [72, dpi]:
        path = tmp_path / f"heading-{resolution}.pdf"
        writer = QPdfWriter(str(path))
        writer.setResolution(resolution)
        writer.setPageMargins(QMarginsF(0, 0, 0, 0))
        height = track.context_track_heading_height(language, 48, writer)
        painter = QPainter(writer)
        painter.scale(resolution / 72, resolution / 72)
        state = (painter.font(), painter.pen(), painter.transform())
        try:
            track.paint_context_track(painter, QRectF(20, 40 + height, 48, 200), events,
                                      0, 10, language, header_height=20 + height)
            assert (painter.font(), painter.pen(), painter.transform()) == state
        finally:
            painter.end()
        with fitz.open(path) as document:
            text = document[0].get_text()
            assert "".join(track.context_heading(language).split()) in "".join(text.split())
            assert "CONN" in text
            spans = [span for block in document[0].get_text("dict")["blocks"] if "lines" in block
                     for line in block["lines"] for span in line["spans"] if span["text"] != "CONN"]
            assert spans
            for span in spans:
                assert span["bbox"][0] >= 19.7
                assert span["bbox"][2] <= 68.3
                assert span["bbox"][3] <= 22 + height + 0.3
            snapshots.append(spans)
    assert len(snapshots[0]) == len(snapshots[1])
    for baseline, actual in zip(*snapshots):
        assert actual["size"] == pytest.approx(baseline["size"], abs=0.08)
        assert actual["bbox"] == pytest.approx(baseline["bbox"], abs=0.3)
    for rect, text, font_size, kwargs in calls:
        assert font_size == size
        assert text == track.context_heading(language)
        assert kwargs == {"point_coordinates": True}
        assert rect.height() > 0
    assert events == before


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [96, 192])
@pytest.mark.parametrize("size", [7.6, 12.0])
def test_raster_context_heading_measures_the_font_it_draws(qapp, monkeypatch, language, dpi, size):
    visual = track.modern_oilfield_report_profile()
    monkeypatch.setattr(track, "modern_oilfield_report_profile",
                        lambda: replace(visual, typography=replace(visual.typography, table_pt=size)))
    image = QImage(300, 500, QImage.Format.Format_ARGB32)
    image.setDotsPerMeterX(round(dpi / 0.0254))
    image.setDotsPerMeterY(round(dpi / 0.0254))
    image.fill("white")
    height = track.context_track_heading_height(language, 96, image, scale=2)
    original = track.paint_track_heading
    calls = []

    def capture(painter, rect, text, font_size, **kwargs):
        calls.append((QRectF(rect), text, font_size, kwargs))
        assert track.track_heading_height(text, rect.width(), font_size, image,
                                          **kwargs) <= rect.height()
        return original(painter, rect, text, font_size, **kwargs)

    monkeypatch.setattr(track, "paint_track_heading", capture)
    painter = QPainter(image)
    try:
        track.paint_context_track(painter, QRectF(20, 60 + height, 96, 200), (),
                                  0, 10, language, header_height=40 + height, scale=2)
    finally:
        painter.end()
    assert len(calls) == 1
    assert calls[0][2] == pytest.approx(size * 2 * 72 / image.logicalDpiY())
    assert calls[0][3] == {"point_coordinates": False}
    assert any(image.pixelColor(x, y).lightness() < 200
               for y in range(24, int(24 + height)) for x in range(20, 116))
