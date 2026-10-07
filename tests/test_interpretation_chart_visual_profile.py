from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import fitz
import numpy as np
import pytest
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as standard
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from test_interpretation_chart_readability import _dataset, _report


def _rgb(color: str) -> tuple[float, ...]:
    return tuple(int(color[index:index + 2], 16) / 255 for index in (1, 3, 5))


@pytest.mark.parametrize("renderer", [standard, enhanced])
@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("grayscale", [False, True])
@pytest.mark.parametrize("landscape", [False, True])
def test_real_pdf_chart_uses_shared_neutral_palette_and_retains_curve_colors(
    qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    renderer: ModuleType, language: AppLanguage, grayscale: bool, landscape: bool,
) -> None:
    profile = modern_oilfield_report_profile(grayscale=grayscale)
    # Distinct colours make stale hard-coded white/text/frame paths observable.
    if not grayscale:
        profile = replace(profile, palette=replace(profile.palette, page="#f1f2e3",
                          text="#192a3b", border="#a1b2c3", border_strong="#617283"))
    for module in (standard, enhanced):
        monkeypatch.setattr(module, "modern_oilfield_report_profile", lambda: profile)
    dataset = _dataset()
    before = deepcopy(dataset)
    output = tmp_path / "chart.pdf"
    writer = QPdfWriter(str(output))
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape if landscape
                              else QPageLayout.Orientation.Portrait)
    painter = QPainter(writer)
    try:
        renderer.render_chart_pages(PageCanvas(writer, painter, language),
                                    _report("opus" if renderer is enhanced else "standard"),
                                    dataset, language)
    finally:
        painter.end()
    with fitz.open(output) as document:
        assert len(document) > 1
        for page in document:
            drawings = page.get_drawings()
            fills = {tuple(round(value, 3) for value in draw["fill"])
                     for draw in drawings if draw["fill"]}
            strokes = {tuple(round(value, 3) for value in draw["color"])
                       for draw in drawings if draw["color"]}
            def normalized(color: str) -> tuple[float, ...]:
                return tuple(round(value, 3) for value in _rgb(color))
            assert normalized(profile.palette.page) in fills
            assert normalized(profile.palette.border) in strokes
            assert normalized(profile.palette.border_strong) in strokes
            # Actual source curves retain their series identity under grayscale chrome.
            assert normalized(standard._COLORS[0]) in strokes
            text_colors = {span["color"] for block in page.get_text("dict")["blocks"]
                           if "lines" in block for line in block["lines"] for span in line["spans"]}
            assert int(profile.palette.text[1:], 16) in text_colors
    assert np.array_equal(dataset.depth, before.depth)
    for identifier, curve in dataset.curves.items():
        assert np.array_equal(curve.values, before.curves[identifier].values)
        assert curve.metadata == before.curves[identifier].metadata
