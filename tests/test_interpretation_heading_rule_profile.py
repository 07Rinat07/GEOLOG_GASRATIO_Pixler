from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as standard
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing import interpretation_track_headings as headings
from geoworkbench.printing.report_painter_fonts import point_coordinate_font
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.localization import AppLanguage
from test_interpretation_chart_readability import _dataset, _geology, _report


_TITLES = {
    AppLanguage.RU: "Общий и нормализованный газ",
    AppLanguage.KK: "Жалпы және нормаланған газ",
    AppLanguage.EN: "Total and normalized gas",
}


@pytest.mark.parametrize("size", [0.0, -1.0, float("nan"), float("inf")])
def test_point_coordinate_font_rejects_invalid_size(qapp: object, size: float) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        point_coordinate_font(size, text="Heading", paint_device=None)


@pytest.mark.parametrize("dpi", [96, 192])
def test_pixel_preview_font_retains_original_coordinate_contract(qapp: object, dpi: int) -> None:
    image = QImage(500, 400, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDotsPerMeterY(round(dpi / 0.0254))
    actual = point_coordinate_font(9.0, text="Қазақша", paint_device=image, bold=True)
    assert actual == print_font(9.0, text="Қазақша", bold=True)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 300, 600])
def test_real_wrapped_heading_preserves_physical_font_and_full_text(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    language: AppLanguage, dpi: int,
) -> None:
    profile = modern_oilfield_report_profile(grayscale=True)
    monkeypatch.setattr(headings, "modern_oilfield_report_profile", lambda: profile)
    title = _TITLES[language]
    output = tmp_path / "heading.pdf"
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    height = headings.track_heading_height(title, 90, 9.0, writer, point_coordinates=True)
    reference = QPdfWriter(str(tmp_path / "reference.pdf"))
    reference.setResolution(72)
    assert height == pytest.approx(headings.track_heading_height(
        title, 90, 9.0, reference, point_coordinates=True), abs=1.0)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        headings.paint_track_heading(painter, QRectF(0, 0, 90, height), title, 9.0,
                                     point_coordinates=True)
    finally:
        painter.end()
    with fitz.open(output) as document:
        page = document[0]
        assert "".join(title.split()) == "".join(page.get_text().split())
        spans = [span for block in page.get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for span in line["spans"]]
        assert spans and all(span["size"] == pytest.approx(9.0, abs=0.08) for span in spans)
        assert all(span["color"] == int(profile.palette.text[1:], 16) for span in spans)


@pytest.mark.parametrize("renderer", [standard, enhanced])
@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 300, 600])
@pytest.mark.parametrize("landscape", [False, True])
def test_real_chart_heading_geometry_and_structural_rules_follow_profile(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    renderer: ModuleType, language: AppLanguage, dpi: int, landscape: bool,
) -> None:
    profile = modern_oilfield_report_profile()
    profile = replace(profile, typography=replace(profile.typography, table_pt=8.6, caption_pt=7.8),
                      layout=replace(profile.layout, thin_rule_pt=1.4, strong_rule_pt=2.2))
    for module in (standard, enhanced, headings):
        monkeypatch.setattr(module, "modern_oilfield_report_profile", lambda: profile)
    observed: list[tuple[str, float, QRectF]] = []
    original = renderer.paint_track_heading
    def capture(painter: QPainter, rect: QRectF, text: str, size: float, **options: Any) -> None:
        assert options["point_coordinates"]
        required = headings.track_heading_height(text, rect.width(), size, painter.device(),
                                                point_coordinates=True)
        assert required <= rect.height() + 1.0
        observed.append((text, size, QRectF(rect)))
        original(painter, rect, text, size, **options)
    monkeypatch.setattr(renderer, "paint_track_heading", capture)
    dataset = _dataset()
    before = {identifier: curve.values.copy() for identifier, curve in dataset.curves.items()}
    output = tmp_path / "chart.pdf"
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape
                              else QPageLayout.Orientation.Portrait)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        options = {"geology": _geology()} if renderer is enhanced else {}
        renderer.render_chart_pages(PageCanvas(writer, painter, language),
                                    _report("opus" if renderer is enhanced else "standard"),
                                    dataset, language, **options)
    finally:
        painter.end()
    assert observed
    assert all(size in (8.6, 7.8) for _, size, _ in observed)
    with fitz.open(output) as document:
        for page in document:
            text = "".join(page.get_text().split())
            for title, _, _ in observed:
                assert "".join(title.split()) in text
            drawings = page.get_drawings()
            assert any(draw["width"] == pytest.approx(1.4, abs=0.03) for draw in drawings)
            for color, width in ((profile.palette.border, 0.7),
                                 (profile.palette.border_strong, 2.2)):
                rgb = tuple(int(color[i:i+2], 16)/255 for i in (1, 3, 5))
                assert any(draw["color"] and all(abs(a-b) < 0.002 for a,b in
                           zip(draw["color"], rgb, strict=True)) and
                           draw["width"] == pytest.approx(width, abs=0.03) for draw in drawings)
    for identifier, values in before.items():
        assert np.array_equal(dataset.curves[identifier].values, values)
