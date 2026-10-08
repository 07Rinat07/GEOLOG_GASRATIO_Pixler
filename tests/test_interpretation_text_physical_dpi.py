from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing import curve_legend_layout as legend_layout
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as standard
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage, chart_geometry
from geoworkbench.printing.gas_ratio_reference import ratio_reference_color
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_interpretation_chart_readability import _dataset, _report


def _spans(page: fitz.Page) -> list[dict[str, Any]]:
    return [span for block in page.get_text("dict")["blocks"] if "lines" in block
            for line in block["lines"] for span in line["spans"]]


@pytest.mark.parametrize("renderer", [standard, enhanced])
@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 300, 600])
@pytest.mark.parametrize("landscape", [False, True])
def test_real_chart_title_axes_and_legends_retain_physical_sizes_and_values(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, renderer: ModuleType,
    language: AppLanguage, dpi: int, landscape: bool,
) -> None:
    profile = modern_oilfield_report_profile()
    profile = replace(profile, typography=replace(profile.typography, table_pt=9.0, caption_pt=8.0))
    for module in (standard, enhanced, legend_layout):
        monkeypatch.setattr(module, "modern_oilfield_report_profile", lambda: profile)
    dataset = _dataset()
    if landscape:
        dataset.depth -= 7000.0
    before = deepcopy(dataset)
    output = tmp_path / "chart.pdf"
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape
                              else QPageLayout.Orientation.Portrait)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        renderer.render_chart_pages(PageCanvas(writer, painter, language),
                                    _report("opus" if renderer is enhanced else "standard"),
                                    dataset, language)
    finally:
        painter.end()
    typography = profile.typography
    title = standard._labels(language)["title"]
    with fitz.open(output) as document:
        assert len(document) > 1
        for page in document:
            spans = _spans(page)
            drawings = page.get_drawings()
            blue = tuple(int(standard._COLORS[0][i:i+2], 16)/255 for i in (1, 3, 5))
            assert any(draw["color"] and all(abs(a-b) < 0.002 for a,b in
                       zip(draw["color"], blue, strict=True)) and
                       draw["width"] == pytest.approx(1.25, abs=0.03) for draw in drawings)
            if renderer is enhanced:
                reference = ratio_reference_color(dataset.curves["WH"]).getRgbF()[:3]
                assert any(draw["color"] and all(abs(a-b) < 0.002 for a,b in
                           zip(draw["color"], reference, strict=True)) and
                           draw["width"] == pytest.approx(0.7, abs=0.03) and
                           not draw["dashes"].startswith("[]") for draw in drawings)
            titles = [span for span in spans if span["text"] == title]
            assert titles and all(span["size"] == pytest.approx(15, abs=0.08) for span in titles)
            percentages = [span for span in spans if span["text"] in ("25", "75")]
            assert percentages and all(span["size"] == pytest.approx(typography.caption_pt, abs=0.08)
                                       for span in percentages)
            axis_numbers = [span for span in spans if
                            span["bbox"][0] < 54 and span["text"].lstrip("-").replace(".", "").isdigit()]
            assert axis_numbers and all(span["size"] == pytest.approx(typography.table_pt, abs=0.08)
                                        for span in axis_numbers)
            if landscape:
                assert all(span["text"].startswith("-") for span in axis_numbers)
            legend = [span for span in spans if "p5=" in span["text"]]
            assert legend and all(span["size"] == pytest.approx(typography.caption_pt, abs=0.08) for span in legend)
        assert str(int(dataset.depth[0])) in document[0].get_text()
    assert np.array_equal(dataset.depth, before.depth)
    for identifier, curve in dataset.curves.items():
        assert np.array_equal(curve.values, before.curves[identifier].values)
        assert curve.metadata == before.curves[identifier].metadata


@pytest.mark.parametrize("renderer", [standard, enhanced])
@pytest.mark.parametrize("dpi", [72, 300, 600])
def test_candidate_code_keeps_physical_size_and_semantic_identity(
    qapp: object, tmp_path: Path, renderer: ModuleType, dpi: int,
) -> None:
    output = tmp_path / "marker.pdf"
    writer = QPdfWriter(str(output))
    writer.setResolution(dpi)
    candidate = SimpleNamespace(top_depth=1020.0, bottom_depth=1040.0,
                                fluid_hypothesis="probable_gas")
    before = deepcopy(candidate)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        page = DepthPage(1000, 1100, 1000, 400)
        if renderer is standard:
            standard._draw_candidate_bands(painter, QRectF(0, 50, 200, 400), page,
                                           (candidate,), show_codes=True)
        else:
            enhanced._draw_visible_fluid_markers(painter, chart_geometry(QRectF(0, 0, 500, 700), page, 3), page,
                                                 (candidate,))
    finally:
        painter.end()
    with fitz.open(output) as document:
        codes = [span for span in _spans(document[0]) if span["text"] == "G"]
        assert codes and all(span["size"] == pytest.approx(5.0 if renderer is standard else 6.0,
                                                         abs=0.08) for span in codes)
    assert candidate == before
