from copy import deepcopy
from dataclasses import replace

import fitz
import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QImage, QPainter, QPdfWriter

from geoworkbench.domain.gas_context_events import GasContextEvent, GasContextEventType
from geoworkbench.printing import gas_context_track as track
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.services.localization import AppLanguage


def _profile(kind):
    visual = track.modern_oilfield_report_profile()
    if kind == "custom":
        return replace(visual, typography=replace(visual.typography, section_pt=26, caption_pt=10.5))
    if kind == "large":
        return replace(visual, typography=replace(visual.typography, section_pt=36, caption_pt=18))
    return visual


def _events(count=3):
    return tuple(GasContextEvent(f"event-{index:03d}-" + "Q" * 100,
                                GasContextEventType.CONNECTION_GAS, index, index + 0.5)
                 for index in range(count))


def _spans(page):
    return [span for block in page.get_text("dict")["blocks"] if "lines" in block
            for line in block["lines"] for span in line["spans"]]


def _snapshot(tmp_path, name, dpi, rows, language):
    path = tmp_path / f"{name}.pdf"
    writer = QPdfWriter(str(path))
    writer.setResolution(dpi)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    height = track.context_legend_height(rows, 500, writer, language=language)
    painter = QPainter(writer)
    painter.scale(dpi / 72, dpi / 72)
    before = (painter.font(), painter.pen(), painter.transform())
    try:
        track.paint_context_legend(painter, QRectF(20, 20, 500, height), rows, language)
        assert (painter.font(), painter.pen(), painter.transform()) == before
    finally:
        painter.end()
    with fitz.open(path) as document:
        return height, document[0].get_text(), _spans(document[0])


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
def test_legend_pdf_roles_and_measured_height_at_print_dpi(qapp, tmp_path, monkeypatch, language, dpi, kind):
    visual = _profile(kind)
    monkeypatch.setattr(track, "modern_oilfield_report_profile", lambda: visual)
    events = _events()
    before = deepcopy(events)
    rows = track.context_legend_rows(track.context_segments(events, -1, 4), language, "m")
    calls = []
    original = track._font_for_device

    def capture(device, size, text):
        calls.append((size, text))
        return original(device, size, text)

    monkeypatch.setattr(track, "_font_for_device", capture)
    baseline = _snapshot(tmp_path, "baseline", 72, rows, language)
    actual = _snapshot(tmp_path, "actual", dpi, rows, language)
    assert actual[0] == pytest.approx(baseline[0], abs=1)
    assert actual[1] == baseline[1]
    assert len(actual[2]) == len(baseline[2])
    assert track.context_title(language) in actual[1]
    flat = "".join(actual[1].split())
    for row in rows:
        assert "".join(row.split()) in flat
    for size, text in calls:
        assert size == (visual.typography.section_pt if text == track.context_title(language)
                        else visual.typography.caption_pt)
    for base, span in zip(baseline[2], actual[2]):
        assert span["size"] == pytest.approx(base["size"], abs=0.08)
        assert span["bbox"] == pytest.approx(base["bbox"], abs=0.3)
        assert span["bbox"][0] >= 19.9 and span["bbox"][2] <= 520.1
        assert span["bbox"][3] <= 20 + actual[0] + 0.3
    title = next(span for span in actual[2] if span["text"] == track.context_title(language))
    assert title["size"] == pytest.approx(visual.typography.section_pt, abs=0.1)
    assert events == before


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
def test_png_legend_uses_same_profile_and_reserved_height(qapp, tmp_path, monkeypatch, language, kind):
    visual = _profile(kind)
    monkeypatch.setattr(track, "modern_oilfield_report_profile", lambda: visual)
    rows = track.context_legend_rows(track.context_segments(_events(), -1, 4), language, "m")
    device = QImage(1, 1, QImage.Format.Format_ARGB32)
    height = track.context_legend_height(rows, 1000, device, scale=2, language=language)
    image = QImage(1040, int(height) + 40, QImage.Format.Format_ARGB32)
    image.fill("white")
    calls = []
    original = track._font_for_device

    def capture(device, size, text):
        calls.append((size, text))
        return original(device, size, text)

    monkeypatch.setattr(track, "_font_for_device", capture)
    painter = QPainter(image)
    try:
        track.paint_context_legend(painter, QRectF(20, 20, 1000, height), rows, language, scale=2)
    finally:
        painter.end()
    for size, text in calls:
        assert size == 2 * (visual.typography.section_pt if text == track.context_title(language)
                           else visual.typography.caption_pt)
    path = tmp_path / "legend.png"
    assert image.save(str(path), "PNG")
    with Image.open(path) as png:
        pixels = np.asarray(png.convert("L"))
    ys, xs = np.where(pixels < 200)
    assert ys.size
    assert ys.min() >= 20
    assert ys.max() < 20 + height
    assert xs.max() < 1020


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
def test_full_context_legend_paginates_using_measured_header(qapp, tmp_path, monkeypatch, language, kind):
    visual = _profile(kind)
    monkeypatch.setattr(track, "modern_oilfield_report_profile", lambda: visual)
    events = _events(60)
    segments = track.context_segments(events, -1, 61)
    rows = track.context_legend_rows(segments, language, "m")
    path = tmp_path / "pages.pdf"
    writer = QPdfWriter(str(path))
    writer.setResolution(72)
    painter = QPainter(writer)
    try:
        canvas = PageCanvas(writer, painter, language)
        track.render_context_legend_pages(canvas, segments, language, "m")
    finally:
        painter.end()
    with fitz.open(path) as document:
        assert len(document) > 1
        flat = "".join("".join(page.get_text().split()) for page in document)
        for row in rows:
            assert "".join(row.split()) in flat
        for page in document:
            assert track.context_title(language) in page.get_text()
            for word in page.get_text("words"):
                assert word[0] >= 0 and word[1] >= 0
                assert word[2] <= page.rect.width + 0.1
                assert word[3] <= page.rect.height + 0.1
