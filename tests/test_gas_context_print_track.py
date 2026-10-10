from copy import deepcopy
from unittest.mock import MagicMock

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.domain.gas_context_events import (
    GasContextEvent, GasContextEventType, GasContextRegistry, InterpretationImpact,
)
from geoworkbench.domain.models import DepthDomain
from geoworkbench.printing import gas_context_track as track
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart as standard
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as enhanced
from geoworkbench.printing import hydrocarbon_interpretation_chart as preview
from geoworkbench.printing.hydrocarbon_interpretation_chart import hydrocarbon_interpretation_chart_data_uri
from geoworkbench.printing.hydrocarbon_interpretation_pdf_canvas import PageCanvas
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage, chart_geometry
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.project.controller import ProjectController
from geoworkbench.services.hydrocarbon_interpretation import build_hydrocarbon_interpretation_report
from geoworkbench.services.localization import AppLanguage
from test_interpretation_report_charts import _session_with_report_curves


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("kind", list(GasContextEventType))
def test_every_event_has_unique_code_and_localized_label(kind, language):
    event = GasContextEvent("event", kind, 0, 1)
    assert track.context_label(event, language)
    assert len(track.context_code(event)) <= 4
    assert len({track.context_code(GasContextEvent("e", k, 0, 1)) for k in GasContextEventType}) == len(GasContextEventType)


def test_context_segments_reuse_registry_priority_and_true_depths():
    events = (
        GasContextEvent("conn", GasContextEventType.CONNECTION_GAS, -10, 10),
        GasContextEvent("trip", GasContextEventType.TRIP_GAS, -2, 4),
        GasContextEvent("repeat", GasContextEventType.CONNECTION_GAS, 12, 14),
        GasContextEvent("draft", GasContextEventType.SWAB_GAS, -8, 8, confirmed=False),
        GasContextEvent("point", GasContextEventType.SWAB_GAS, 5, 5),
    )
    before = deepcopy(events)
    segments = track.context_segments(events, -5, 15)
    assert [(s.event.event_id, s.top_depth, s.bottom_depth) for s in segments] == [
        ("conn", -5, -2), ("trip", -2, 4), ("conn", 4, 10), ("point", 5, 5), ("repeat", 12, 14),
    ]
    registry = GasContextRegistry(events)
    for s in segments:
        assert registry.resolve_at_depth((s.top_depth + s.bottom_depth) / 2) == s.event
    assert events == before


def test_hard_exclusions_and_drafts_do_not_enter_customer_track():
    events = (
        GasContextEvent("excluded", GasContextEventType.CALIBRATION_GAS, 0, 5),
        GasContextEvent("draft", GasContextEventType.TRIP_GAS, 0, 5, confirmed=False),
    )
    assert track.context_segments(events, 0, 10) == ()
    legacy = chart_geometry(QRectF(0, 0, 600, 800), DepthPage(0, 10, 1000, 400), 3)
    with_track = chart_geometry(QRectF(0, 0, 600, 800), DepthPage(0, 10, 1000, 400), 3, context_track=True)
    assert legacy.context_rect is None
    assert with_track.context_rect.right() < with_track.panel_rects[0].left()
    assert with_track.panel_rects[-1].right() < with_track.right_axis_rect.left()
    assert legacy.left_axis_rect == with_track.left_axis_rect


@pytest.mark.parametrize("impact", [InterpretationImpact.TECHNOLOGICAL_GAS, InterpretationImpact.FORMATION_GAS, InterpretationImpact.REVIEW_REQUIRED])
def test_track_retains_monochrome_text_styles_and_clips_tiny_bands(qapp, monkeypatch, impact):
    profile = modern_oilfield_report_profile(grayscale=True)
    monkeypatch.setattr(track, "modern_oilfield_report_profile", lambda: profile)
    painter = MagicMock()
    painter.device.return_value.logicalDpiY.return_value = 72
    events = (GasContextEvent("conn", GasContextEventType.CONNECTION_GAS, 0, 5, impact=impact),
              GasContextEvent("tiny", GasContextEventType.TRIP_GAS, 8, 8.001, impact=impact))
    track.paint_context_track(painter, QRectF(0, 30, 48, 100), events, 0, 10, AppLanguage.EN, header_height=30)
    assert any(c.args[-1] == "CONN" for c in painter.drawText.call_args_list)
    assert not any(c.args[-1] == "TRIP" for c in painter.drawText.call_args_list)
    assert any(getattr(c.args[0], "style", lambda: None)() == track._STYLES[impact] for c in painter.setPen.call_args_list)
    bands = [c.args[0] for c in painter.drawRect.call_args_list][1:]
    assert bands[0].top() == 30
    assert bands[0].bottom() == 80
    assert bands[1].top() == 110
    assert painter.save.call_count == painter.restore.call_count


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("renderer", [standard, enhanced])
def test_save_reopen_context_pdf_and_preview_share_registry(qapp, tmp_path, monkeypatch, language, renderer):
    session = _session_with_report_curves(depth_start=0, depth_span=120)
    session.current_well.gas_context_events.extend([
        GasContextEvent("connection-one", GasContextEventType.CONNECTION_GAS, 5, 40, depth_domain=DepthDomain.MD),
        GasContextEvent("trip-one", GasContextEventType.TRIP_GAS, 20, 30, depth_domain=DepthDomain.MD),
        GasContextEvent("connection-two", GasContextEventType.CONNECTION_GAS, 95, 115, depth_domain=DepthDomain.MD),
        GasContextEvent("excluded", GasContextEventType.CALIBRATION_GAS, 70, 80, depth_domain=DepthDomain.MD),
        GasContextEvent("draft", GasContextEventType.SWAB_GAS, 50, 60, depth_domain=DepthDomain.MD, confirmed=False),
    ])
    target = tmp_path / "context.geologpkg"
    ProjectController(session=session).save_project(target)
    restored = ProjectController().open_project(target)
    dataset = restored.current_dataset
    arrays = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    events = deepcopy(restored.current_well.gas_context_events)
    report = build_hydrocarbon_interpretation_report(restored)
    before = deepcopy(report)
    pdf = tmp_path / "context.pdf"
    writer = QPdfWriter(str(pdf))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setResolution(72)
    painter = QPainter(writer)
    try:
        renderer.render_chart_pages(PageCanvas(writer, painter, language), report, dataset, language)
    finally:
        painter.end()
    with fitz.open(pdf) as doc:
        text = "\n".join(p.get_text() for p in doc)
        assert track.context_title(language) in text
        assert track.context_label(events[0], language) in text
        assert "connection-one" in text and "connection-two" in text and "trip-one" in text
        assert "CONN" in text and "TRIP" in text
        assert "excluded" not in text and "draft" not in text
        assert any(d.get("dashes") not in (None, "[] 0") for p in doc for d in p.get_drawings())
    preview_rows = []
    original = preview.paint_context_legend
    def record_legend(painter, rect, rows, output_language, **kwargs):
        preview_rows.extend(rows)
        original(painter, rect, rows, output_language, **kwargs)
    monkeypatch.setattr(preview, "paint_context_legend", record_legend)
    assert hydrocarbon_interpretation_chart_data_uri(report, dataset, language).startswith("data:image/png;base64,")
    assert tuple(preview_rows) == track.context_legend_rows(track.context_segments(report.gas_context_events, 0, 120), language, report.depth_unit)
    assert restored.current_well.gas_context_events == events
    assert report.gas_context_events == before.gas_context_events
    assert report.candidates == before.candidates
    for key, values in arrays.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 300, 600])
def test_context_text_remains_physical_and_complete_at_printer_dpi(qapp, tmp_path, monkeypatch, language, dpi):
    profile = modern_oilfield_report_profile(grayscale=True)
    monkeypatch.setattr(track, "modern_oilfield_report_profile", lambda: profile)
    event = GasContextEvent("connection-one", GasContextEventType.CONNECTION_GAS, 0, 10)
    segments = track.context_segments((event,), 0, 20)
    pdf = tmp_path / "context-dpi.pdf"
    writer = QPdfWriter(str(pdf))
    writer.setResolution(dpi)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72, dpi / 72)
        track.paint_context_track(painter, QRectF(20, 70, 48, 200), (event,), 0, 20, language, header_height=50)
        track.paint_context_legend(painter, QRectF(20, 300, 500, 100), track.context_legend_rows(segments, language, "m"), language)
    finally:
        painter.end()
    with fitz.open(pdf) as doc:
        text = doc[0].get_text()
        assert "connection-one" in text and "0–10 m" in text
        assert track.context_label(event, language) in text
        spans = [s for b in doc[0].get_text("dict")["blocks"] if "lines" in b for line in b["lines"] for s in line["spans"]]
        code = next(s for s in spans if s["text"] == "CONN")
        assert code["size"] == pytest.approx(6.0, abs=0.05)
        assert code["color"] == int(profile.palette.text.lstrip("#"), 16)
        assert code["bbox"][1] >= 70 and code["bbox"][3] <= 170


def test_dense_repeated_events_paginate_complete_legend_without_id_loss(qapp, tmp_path):
    events = tuple(GasContextEvent(f"event-{i:03d}-" + "Q" * 180, GasContextEventType.CONNECTION_GAS,
                                  i / 10, (i + 0.9) / 10) for i in range(100))
    segments = track.context_segments(events, 0, 10)
    assert len(segments) == 100
    pdf = tmp_path / "dense.pdf"
    writer = QPdfWriter(str(pdf))
    writer.setResolution(72)
    painter = QPainter(writer)
    try:
        canvas = PageCanvas(writer, painter, AppLanguage.EN)
        track.render_context_legend_pages(canvas, segments, AppLanguage.EN, "m")
    finally:
        painter.end()
    with fitz.open(pdf) as doc:
        assert len(doc) > 1
        text = "\n".join(p.get_text() for p in doc)
        for i in range(100):
            assert f"event-{i:03d}-" in text
        assert "Q" * 180 in text.replace("\n", "")
        for page in doc:
            for word in page.get_text("words"):
                assert word[0] >= -0.1 and word[1] >= -0.1
                assert word[2] <= page.rect.width + 0.1
                assert word[3] <= page.rect.height + 0.1

@pytest.mark.parametrize("depth,expected_y", ((0.0, 30.0), (5.0, 80.0), (10.0, 130.0)))
@pytest.mark.parametrize("impact", (
    InterpretationImpact.TECHNOLOGICAL_GAS,
    InterpretationImpact.FORMATION_GAS,
    InterpretationImpact.REVIEW_REQUIRED,
))
def test_point_event_has_visible_monochrome_depth_tick_without_zero_height_band(
    qapp, monkeypatch, depth, expected_y, impact,
):
    profile = modern_oilfield_report_profile(grayscale=True)
    monkeypatch.setattr(track, "modern_oilfield_report_profile", lambda: profile)
    monkeypatch.setattr(track, "paint_track_heading", lambda *args, **kwargs: None)
    event = GasContextEvent("point", GasContextEventType.CONNECTION_GAS,
                            depth, depth, impact=impact)
    original = deepcopy(event)
    painter = MagicMock()
    painter.device.return_value.logicalDpiY.return_value = 72
    track.paint_context_track(
        painter, QRectF(0, 30, 48, 100), (event,), 0, 10,
        AppLanguage.EN, header_height=30,
    )
    assert painter.drawLine.call_count == 1
    marker = painter.drawLine.call_args.args[0]
    assert marker.length() > 0.0
    assert marker.y1() == pytest.approx(expected_y)
    assert marker.y2() == pytest.approx(expected_y)
    assert marker.x1() > 0.0 and marker.x2() < 48.0
    assert painter.drawRect.call_count == 1  # plot border, no empty event band
    assert painter.setPen.call_args.args[0].style() == track._STYLES[impact]
    assert painter.save.call_count == painter.restore.call_count
    assert event == original
    assert "point" in track.context_legend_rows(
        track.context_segments((event,), 0, 10), AppLanguage.EN, "m"
    )[0]


def test_point_event_depth_tick_is_vector_geometry_in_grayscale_pdf(
    qapp, tmp_path, monkeypatch,
):
    profile = modern_oilfield_report_profile(grayscale=True)
    monkeypatch.setattr(track, "modern_oilfield_report_profile", lambda: profile)
    event = GasContextEvent("point-pdf", GasContextEventType.CONNECTION_GAS, 5, 5)
    pdf = tmp_path / "point-event.pdf"
    writer = QPdfWriter(str(pdf))
    writer.setResolution(72)
    painter = QPainter(writer)
    try:
        track.paint_context_track(
            painter, QRectF(20, 70, 48, 200), (event,), 0, 10,
            AppLanguage.EN, header_height=50,
        )
    finally:
        painter.end()
    with fitz.open(pdf) as document:
        drawings = document[0].get_drawings()
        # Compare PDF vector paths in the same coordinate system: printer
        # margins can translate both the frame and the tick together.
        frames = [
            item[1] for drawing in drawings for item in drawing["items"]
            if item[0] == "re"
            and abs(item[1].width - 48.0) < 2.0
            and abs(item[1].height - 200.0) < 2.0
        ]
        assert frames, "The PDF must contain a vector track frame"
        frame = frames[0]
        lines = [
            item for drawing in drawings for item in drawing["items"]
            if item[0] == "l"
        ]
        assert any(
            abs(item[1].y - (frame.y0 + frame.height / 2.0)) <= 0.5
            and abs(item[2].y - (frame.y0 + frame.height / 2.0)) <= 0.5
            and abs(item[1].x - item[2].x) >= 35.0
            for item in lines
        ), "A point must be a full-width vector tick at the actual depth"


def test_point_at_shared_page_seam_is_owned_only_by_next_page(qapp, monkeypatch):
    monkeypatch.setattr(track, "paint_track_heading", lambda *args, **kwargs: None)
    event = GasContextEvent("seam", GasContextEventType.CONNECTION_GAS, 10, 10)
    assert track.context_segments((event,), 0, 10, include_bottom_point=False) == ()
    assert track.context_segments((event,), 10, 20, include_bottom_point=True) == (
        track.GasContextSegment(event, 10, 10),
    )
    first = MagicMock()
    first.device.return_value.logicalDpiY.return_value = 72
    second = MagicMock()
    second.device.return_value.logicalDpiY.return_value = 72
    track.paint_context_track(
        first, QRectF(0, 30, 48, 100), (event,), 0, 10,
        AppLanguage.EN, header_height=30, include_bottom_point=False,
    )
    track.paint_context_track(
        second, QRectF(0, 30, 48, 100), (event,), 10, 20,
        AppLanguage.EN, header_height=30, include_bottom_point=True,
    )
    first.drawLine.assert_not_called()
    second.drawLine.assert_called_once()
    assert second.drawLine.call_args.args[0].y1() == pytest.approx(30.0)
    # The final page includes its own bottom endpoint.
    assert track.context_segments(
        (event,), 0, 10, include_bottom_point=True,
    ) == (track.GasContextSegment(event, 10, 10),)


def test_point_marker_paints_above_coincident_interval_fill(qapp, monkeypatch):
    monkeypatch.setattr(track, "paint_track_heading", lambda *args, **kwargs: None)
    band = GasContextEvent("band", GasContextEventType.CONNECTION_GAS, 0, 10)
    point = GasContextEvent("point", GasContextEventType.SWAB_GAS, 0, 0)
    assert GasContextRegistry((band, point)).resolve_at_depth(0) == point
    painter = MagicMock()
    painter.device.return_value.logicalDpiY.return_value = 72
    track.paint_context_track(
        painter, QRectF(0, 30, 48, 100), (band, point), 0, 10,
        AppLanguage.EN, header_height=30,
    )
    draw_calls = [name for name, _args, _kwargs in painter.method_calls]
    assert draw_calls.count("drawLine") == 1
    assert draw_calls.count("drawRect") == 2
    assert draw_calls.index("drawLine") > max(
        i for i, name in enumerate(draw_calls) if name == "drawRect"
    )
    assert painter.drawLine.call_args.args[0].y1() == pytest.approx(30.0)
