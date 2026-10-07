from copy import deepcopy
from dataclasses import replace
import base64
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPdfWriter

from geoworkbench.printing import hydrocarbon_interpretation_geology_legend as renderer
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing import hydrocarbon_interpretation_chart as preview
from geoworkbench.printing.hydrocarbon_interpretation_report import export_hydrocarbon_interpretation_pdf
from geoworkbench.printing.report_visual_system import ReportVisualProfile, modern_oilfield_report_profile
from geoworkbench.services.localization import AppLanguage
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report, build_opus_interpretation_report
from test_interpretation_chart_readability import _geology
from test_hydrocarbon_interpretation import _session


def _profile(grayscale: bool = False) -> ReportVisualProfile:
    profile = modern_oilfield_report_profile(grayscale=grayscale)
    return replace(profile, typography=replace(profile.typography, table_pt=9.0, caption_pt=8.0),
                   layout=replace(profile.layout, thin_rule_pt=1.2))


@pytest.mark.parametrize("width", [360, 500, 760])
@pytest.mark.parametrize("profile", [modern_oilfield_report_profile(), _profile()])
def test_compact_legend_stays_smaller_with_profile_sized_text(qapp: object, monkeypatch: pytest.MonkeyPatch, width: float, profile: ReportVisualProfile) -> None:
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: profile)
    legend = renderer.InterpretationGeologyLegend(tuple(
        renderer.GeologyLegendItem("lithology", f"rock-{index}", f"R{index}", f"Lithology {index}")
        for index in range(12)
    ))
    assert renderer.geology_legend_height(width, legend, compact=True) < renderer.geology_legend_height(width, legend)


@pytest.mark.parametrize("grayscale", [False, True])
def test_legend_chrome_and_fonts_follow_profile_without_recoloring_geology(qapp: object, monkeypatch: pytest.MonkeyPatch, grayscale: bool) -> None:
    visual = _profile(grayscale)
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: visual)
    legend = renderer.InterpretationGeologyLegend((
        renderer.GeologyLegendItem("lithology", "rock", "SS", "Sandstone", "#d8b26e", "sandstone_bricks"),
        renderer.GeologyLegendItem("lba-type", "bitumen", "MB", "Oily bitumen", "#f59e0b", intensity=3),
        renderer.GeologyLegendItem("lba-color", "colour", "GY", "Greenish yellow", "#faff00"),
    ))
    before = deepcopy(legend)
    image = QImage(600, 300, QImage.Format.Format_ARGB32_Premultiplied)
    painter = MagicMock()
    painter.device.return_value = image
    patterns: list[tuple[str, str]] = []
    intensities: list[tuple[Any, ...]] = []
    def brush(_painter: QPainter, color: str, pattern: str) -> QBrush:
        patterns.append((color, pattern))
        return QBrush(QColor(color))
    monkeypatch.setattr(renderer, "masterlog_lithology_brush", brush)
    monkeypatch.setattr(renderer, "paint_lba_intensity_symbol", lambda *args: intensities.append(args))
    renderer.paint_geology_legend(painter, QRectF(0, 0, 600, 250), legend, AppLanguage.EN)
    assert painter.fillRect.call_args_list[0].args[1].name() == visual.palette.page
    pens = [call.args[0] for call in painter.setPen.call_args_list]
    assert any(hasattr(pen, "widthF") and pen.widthF() == 1.2 and pen.color().name() == visual.palette.border for pen in pens)
    assert {color.name() for color in pens if isinstance(color, QColor)} >= {visual.palette.text, visual.palette.text_secondary}
    sizes = {call.args[0].pointSizeF() for call in painter.setFont.call_args_list}
    assert 9.0 in sizes and 8.0 in sizes
    assert patterns == [("#d8b26e", "sandstone_bricks")]
    assert intensities[0][4].name() == "#f59e0b" and intensities[0][5] == 3
    assert legend == before


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 300, 600])
@pytest.mark.parametrize("compact", [False, True])
def test_real_pdf_legend_has_profile_point_sizes_at_every_device_dpi(qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: AppLanguage, dpi: int, compact: bool) -> None:
    visual = _profile()
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: visual)
    legend = renderer.build_interpretation_geology_legend(_geology(), 1000, 1350, language)
    target = tmp_path / "legend.pdf"
    writer = QPdfWriter(str(target))
    writer.setResolution(dpi)
    height = renderer.geology_legend_height(500, legend, compact=compact, paint_device=writer)
    assert height < 400
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        renderer.paint_geology_legend(painter, QRectF(0, 0, 500, height), legend, language, compact=compact)
    finally:
        painter.end()
    with fitz.open(target) as document:
        page = document[0]
        text = "".join(page.get_text().split())
        for item in legend.items:
            assert "".join(f"{item.code} — {item.label}".split()) in text
        spans = [span for block in page.get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for span in line["spans"]]
        body = [span for span in spans if "Sandstone" in span["text"] or "Құмтас" in span["text"] or "Песчаник" in span["text"]]
        assert body and all(span["size"] == pytest.approx(8 if compact else 9, abs=0.08) for span in body)
        border = tuple(int(visual.palette.border[i:i + 2], 16) / 255 for i in (1, 3, 5))
        assert any(drawing["color"] and all(abs(a-b) < 0.002 for a, b in zip(drawing["color"], border, strict=True))
                   and drawing["width"] == pytest.approx(1.2, abs=0.03) for drawing in page.get_drawings())


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("profile", ["standard", "opus"])
def test_real_chart_and_png_paths_apply_profile_legend_without_source_mutation(qapp: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, language: AppLanguage, profile: str) -> None:
    visual = _profile()
    visual = replace(visual, palette=replace(visual.palette, page="#f2f3f4"))
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: visual)
    geology = _geology()
    before = deepcopy(geology)
    package = tmp_path / "legend.geologpkg"
    ProjectController(session=_session()).save_project(package)
    reopened = ProjectController().open_project(package)
    dataset = reopened.current_dataset
    assert dataset is not None
    builder = build_hydrocarbon_interpretation_report if profile == "standard" else build_opus_interpretation_report
    report = builder(reopened)
    arrays = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    legends: list[renderer.InterpretationGeologyLegend] = []
    original = renderer.paint_geology_legend
    def record(*args: Any, **kwargs: Any) -> None:
        legends.append(args[2])
        return original(*args, **kwargs)
    # The production exporter uses the geology-capable chart adapter for both
    # report kinds whenever geological tracks are present.
    monkeypatch.setattr(enhanced, "paint_geology_legend", record)
    monkeypatch.setattr(preview, "paint_geology_legend", record)
    target = tmp_path / "chart.pdf"
    export_hydrocarbon_interpretation_pdf(report, target, dataset=dataset, language=language, include_chart=True, geology=geology)
    uri = preview.hydrocarbon_interpretation_chart_data_uri(report, dataset, language, geology=geology)
    image = QImage.fromData(base64.b64decode(uri.split(",", 1)[1]))
    assert image.pixelColor(92, 74).name() == visual.palette.page
    assert len(legends) >= 2 and all(not legend.empty for legend in legends)
    with fitz.open(target) as document:
        text = "".join(" ".join(page.get_text() for page in document).split())
        expected = renderer.build_interpretation_geology_legend(
            geology, float(np.nanmin(dataset.depth)), float(np.nanmax(dataset.depth)), language,
        )
        for item in expected.items:
            label = f"{item.code} — {item.label}" if item.code else item.label
            assert "".join(label.split()) in text
    assert geology == before
    for key, values in arrays.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
