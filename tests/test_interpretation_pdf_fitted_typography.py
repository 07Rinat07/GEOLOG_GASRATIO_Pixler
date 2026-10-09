from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as standard
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing import report_painter_fonts as fonts
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage, chart_geometry
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_charts import _session_with_report_curves


def _profile(kind):
    visual = standard.modern_oilfield_report_profile()
    if kind == "default":
        return visual
    size = 18 if kind == "custom" else 36
    return replace(visual, typography=replace(visual.typography, title_pt=size, subtitle_pt=size,
                                              body_pt=size, caption_pt=size))


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
@pytest.mark.parametrize("role", ["title", "subtitle", "empty", "code"])
def test_fitted_profile_text_remains_complete_at_physical_dpi(qapp, tmp_path, language, dpi, kind, role):
    visual = _profile(kind)
    labels = standard._labels(language)
    text, size, width, height = {
        "title": (labels["title"], visual.typography.title_pt, 300, 25),
        "subtitle": (labels["page"].format(current=1, total=2, top=-120, bottom=-20, unit="m", scale=1000),
                     visual.typography.subtitle_pt, 300, 20),
        "empty": (labels["no_data"], visual.typography.body_pt, 80, 100),
        "code": ("L/GC", visual.typography.caption_pt, 19, 11),
    }[role]
    snapshots = []
    for resolution in [72, dpi]:
        target = tmp_path / f"text-{resolution}.pdf"
        writer = QPdfWriter(str(target))
        writer.setResolution(resolution)
        writer.setPageMargins(QMarginsF(0, 0, 0, 0))
        painter = QPainter(writer)
        painter.scale(resolution / 72, resolution / 72)
        state = (painter.font(), painter.pen(), painter.transform())
        try:
            fonts.paint_fitted_point_text(painter, QRectF(20, 20, width, height), text, size,
                                          visual.palette.text, Qt.AlignmentFlag.AlignCenter,
                                          bold=role in {"title", "code"})
            assert (painter.font(), painter.pen(), painter.transform()) == state
        finally:
            painter.end()
        with fitz.open(target) as document:
            assert "".join(document[0].get_text().split()) == "".join(text.split())
            spans = [span for block in document[0].get_text("dict")["blocks"] if "lines" in block
                     for line in block["lines"] for span in line["spans"]]
            assert spans
            for span in spans:
                assert span["bbox"][0] >= 19.7 and span["bbox"][2] <= 20 + width + 0.3
                assert span["bbox"][1] >= 19.7 and span["bbox"][3] <= 20 + height + 0.3
            snapshots.append(spans)
    assert len(snapshots[0]) == len(snapshots[1])
    for baseline, actual in zip(*snapshots):
        assert actual["size"] == pytest.approx(baseline["size"], abs=0.1)
        assert actual["bbox"] == pytest.approx(baseline["bbox"], abs=0.3)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
@pytest.mark.parametrize("renderer", [standard, enhanced])
def test_both_pdf_adapters_request_profile_after_reopen(qapp, tmp_path, monkeypatch, language, kind, renderer):
    visual = _profile(kind)
    monkeypatch.setattr(standard, "modern_oilfield_report_profile", lambda: visual)
    monkeypatch.setattr(enhanced, "modern_oilfield_report_profile", lambda: visual)
    controller = ProjectController(session=_session_with_report_curves(depth_start=-120, depth_span=100))
    target = tmp_path / "project.geoproj"
    controller.save_project(target)
    restored = ProjectController().open_project(target)
    dataset = restored.current_dataset
    arrays = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    report = build_hydrocarbon_interpretation_report(restored)
    before = deepcopy(report)
    requests = []
    original = renderer.paint_fitted_point_text

    def capture(painter, rect, text, size, color, flags, **kwargs):
        requests.append((text, size))
        return original(painter, rect, text, size, color, flags, **kwargs)

    monkeypatch.setattr(renderer, "paint_fitted_point_text", capture)
    pdf = tmp_path / "chart.pdf"
    writer = QPdfWriter(str(pdf))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setResolution(300)
    painter = QPainter(writer)
    painter.scale(300 / 72, 300 / 72)
    try:
        renderer.render_chart_pages(PageCanvas(writer, painter, language), report, dataset, language)
    finally:
        painter.end()
    labels = standard._labels(language)
    assert (labels["title"], visual.typography.title_pt) in requests
    subtitles = [(text, size) for text, size in requests if "-120" in text]
    assert subtitles and all(size == visual.typography.subtitle_pt for text, size in subtitles)
    with fitz.open(pdf) as document:
        text = "".join("".join(page.get_text().split()) for page in document)
        assert "".join(labels["title"].split()) in text
    assert report.candidates == before.candidates and report.gas_context_events == before.gas_context_events
    for key, values in arrays.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", ["default", "custom", "large"])
@pytest.mark.parametrize("renderer", [standard, enhanced])
def test_empty_panels_and_candidate_codes_request_body_and_caption(qapp, tmp_path, monkeypatch, language, kind, renderer):
    visual = _profile(kind)
    monkeypatch.setattr(renderer, "modern_oilfield_report_profile", lambda: visual)
    dataset = _session_with_report_curves().current_dataset
    requests = []
    original = renderer.paint_fitted_point_text

    def capture(painter, rect, text, size, color, flags, **kwargs):
        requests.append((text, size))
        return original(painter, rect, text, size, color, flags, **kwargs)

    monkeypatch.setattr(renderer, "paint_fitted_point_text", capture)
    writer = QPdfWriter(str(tmp_path / "empty-codes.pdf"))
    writer.setResolution(72)
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    painter = QPainter(writer)
    page = DepthPage(0, 10, 1000, 400)
    candidate = SimpleNamespace(top_depth=2, bottom_depth=4, fluid_hypothesis="probable_gas")
    before = deepcopy(candidate)
    try:
        renderer._draw_panel(painter, QRectF(20, 100, 220, 100), page, dataset,
                             "total", (), {}, (), language)
        if renderer is standard:
            renderer._draw_candidate_bands(painter, QRectF(20, 300, 220, 100), page,
                                           (candidate,), show_codes=True)
        else:
            renderer._draw_visible_fluid_markers(painter,
                chart_geometry(QRectF(20, 250, 700, 400), page, 3), page, (candidate,))
    finally:
        painter.end()
    assert requests == [(standard._labels(language)["no_data"], visual.typography.body_pt),
                        ("G", visual.typography.caption_pt)]
    with fitz.open(tmp_path / "empty-codes.pdf") as document:
        text = "".join(document[0].get_text().split())
        assert "".join(standard._labels(language)["no_data"].split()) in text
        assert "G" in text
    assert candidate == before
