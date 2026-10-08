from dataclasses import replace
from types import SimpleNamespace

import fitz
import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QFont, QPainter, QPdfWriter
from PySide6.QtPrintSupport import QPrinter

from geoworkbench.printing import document_renderer as renderer
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.printing.unicode_support import resolve_unicode_font_profile
from geoworkbench.services.localization import AppLanguage, Localizer


TITLES = {"ru": "Газовый каротаж", "kk": "Газ Әғқң", "en": "Gas logging"}
RANGE = "-12.5–1500 m"


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("width", [100, 180, 520])
@pytest.mark.parametrize("padding", [8, 14])
@pytest.mark.parametrize("device_kind", ["writer", "printer"])
def test_tablet_header_footer_keep_physical_gap_and_unicode_pdf(
    qapp, tmp_path, monkeypatch, language, dpi, width, padding, device_kind
):
    profile = modern_oilfield_report_profile()
    profile = replace(profile, layout=replace(profile.layout, card_padding_pt=padding))
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: profile)
    localizer = Localizer.create(language)
    page = SimpleNamespace(index=999, total=999)
    number = localizer.text("print_center.page_number", page=999, total=999)
    old_font = QFont(qapp.font())
    calls = []
    original_print_font = renderer.point_coordinate_font

    def capture_font(*args, **kwargs):
        font = original_print_font(*args, **kwargs)
        calls.append((kwargs["text"], font.families()))
        return font

    monkeypatch.setattr(renderer, "point_coordinate_font", capture_font)
    snapshots = []
    try:
        qapp.setFont(QFont("Courier New", 19))
        for index, resolution in enumerate((72, dpi)):
            target = tmp_path / f"spacing-{index}.pdf"
            if device_kind == "writer":
                writer = QPdfWriter(str(target))
                writer.setPageMargins(QMarginsF(0, 0, 0, 0))
            else:
                writer = QPrinter(QPrinter.PrinterMode.HighResolution)
                writer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                writer.setOutputFileName(str(target))
                writer.setFullPage(True)
            writer.setResolution(resolution)
            painter = QPainter(writer)
            scale = resolution / 72
            drawn = []

            class CapturePainter:
                def __getattr__(self, name):
                    return getattr(painter, name)

                def drawText(self, rect, flags, text):
                    drawn.append((QRectF(rect), text))
                    painter.drawText(rect, flags, text)

            previous_font, previous_pen = QFont(painter.font()), painter.pen()
            try:
                proxy = CapturePainter()
                renderer._paint_header(proxy, QRectF(0, 0, width * scale, 28 * scale),
                                       title=TITLES[language.value] * 8, range_text=RANGE)
                renderer._paint_footer(proxy, QRectF(0, 70 * scale, width * scale, 24 * scale),
                                       page=page, show_page_numbers=True, localizer=localizer)
                assert painter.font() == previous_font
                assert painter.pen() == previous_pen
            finally:
                painter.end()
            with fitz.open(target) as document:
                text = document[0].get_text()
                assert RANGE in text
                assert number in text
                spans = [span for block in document[0].get_text("dict")["blocks"]
                         if "lines" in block for line in block["lines"] for span in line["spans"]]
                range_span = next(span for span in spans if span["text"] == RANGE)
                number_span = next(span for span in spans if span["text"] == number)
                title_spans = [span for span in spans if span["bbox"][1] < 40 and span is not range_span]
                brand_spans = [span for span in spans if span["bbox"][1] >= 40 and span is not number_span]
                assert title_spans and brand_spans
                assert max(span["bbox"][2] for span in title_spans) <= range_span["bbox"][0] - padding + 1
                assert max(span["bbox"][2] for span in brand_spans) <= number_span["bbox"][0] - padding + 1
                for span in spans:
                    assert span["bbox"][0] >= -0.5 and span["bbox"][2] <= width + 0.5
                snapshots.append(([rect.width() for rect, _ in drawn], spans))
    finally:
        qapp.setFont(old_font)
    assert len(calls) == 6
    for text, families in calls:
        assert families == list(resolve_unicode_font_profile(text).families)
    assert any(number in text and profile.brand_wordmark in text for text, _ in calls)
    assert snapshots[1][0] == pytest.approx(snapshots[0][0], abs=0.5)
    for text in (RANGE, number):
        baseline = next(span for span in snapshots[0][1] if span["text"] == text)
        actual = next(span for span in snapshots[1][1] if span["text"] == text)
        assert actual["size"] == pytest.approx(baseline["size"], abs=0.1)
        assert actual["bbox"] == pytest.approx(baseline["bbox"], abs=0.8)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_empty_range_and_hidden_page_number_use_full_width(qapp, tmp_path, language):
    writer = QPdfWriter(str(tmp_path / "no-number.pdf"))
    painter = QPainter(writer)
    before = QFont(painter.font()), painter.pen()
    try:
        renderer._paint_header(painter, QRectF(0, 0, 800, 80), title=TITLES[language.value], range_text="")
        renderer._paint_footer(painter, QRectF(0, 100, 800, 80), page=SimpleNamespace(index=1, total=1),
                               show_page_numbers=False, localizer=Localizer.create(language))
        assert (painter.font(), painter.pen()) == before
    finally:
        painter.end()
