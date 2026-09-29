from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as chart
from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import DepthPage, plan_depth_pages
from geoworkbench.printing.hydrocarbon_interpretation_report_range import ReportDepthRange
from geoworkbench.services.localization import AppLanguage


def _dataset() -> Dataset:
    return Dataset(
        dataset_id="dataset-chart-range",
        name="Chart range",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([47.0, 1980.0, 2016.2, 2200.0], dtype=np.float64),
    )


def test_chart_page_planner_uses_selected_report_depth_range(monkeypatch) -> None:
    observed: list[tuple[float, float, float]] = []

    monkeypatch.setattr(
        chart.base_chart,
        "_panel_curves",
        lambda report, dataset: (("gas", (object(),)),),
    )
    monkeypatch.setattr(chart.base_chart, "_curve_ranges", lambda panels, dataset: {})

    def _plan(top: float, bottom: float, available: float):
        observed.append((top, bottom, available))
        return ()

    monkeypatch.setattr(chart, "plan_depth_pages", _plan)
    canvas = SimpleNamespace(content_rect=QRectF(0.0, 0.0, 842.0, 560.0))
    report = SimpleNamespace(depth_unit="m")

    chart.render_chart_pages(
        canvas,
        report,  # type: ignore[arg-type]
        _dataset(),
        AppLanguage.RU,
        depth_range=ReportDepthRange(1980.0, 2016.2),
    )

    assert len(observed) == 1
    assert observed[0][0:2] == (1980.0, 2016.2)
    assert observed[0][2] > 0.0


def test_short_interpretation_interval_fills_printable_chart_height() -> None:
    available = 360.0
    pages = plan_depth_pages(4313.7, 4389.7, available)

    assert len(pages) == 1
    assert pages[0].scale_denominator == 600
    assert pages[0].plot_height_points >= available * 0.95


def test_long_interpretation_range_has_even_page_density_without_short_tail() -> None:
    available = 360.0
    pages = plan_depth_pages(51.0, 5549.0, available)

    assert 1 < len(pages) <= 80
    assert max(page.span for page in pages) <= 105.0
    heights = [page.plot_height_points for page in pages]
    assert min(heights) >= available * 0.82
    assert max(heights) - min(heights) <= 1.0
    assert pages[0].top_depth == 51.0
    assert pages[-1].bottom_depth == 5549.0


def test_print_curve_remains_visible_for_nearly_constant_signal(qapp) -> None:
    depth = np.linspace(100.0, 110.0, 101)
    dataset = Dataset(
        dataset_id="dataset-print-contrast",
        name="Print contrast",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=depth,
    )
    curve = dataset.upsert_curve(
        "OPUS3",
        np.full(depth.shape, 1.0, dtype=np.float64),
    )
    panels = (("opus", (curve,)),)
    page = DepthPage(100.0, 110.0, 100, 300.0)
    ranges = chart.base_chart._curve_ranges(panels, dataset, page=page)

    assert curve.metadata.curve_id in ranges
    low, high = ranges[curve.metadata.curve_id]
    assert low < 1.0 < high

    image = QImage(420, 360, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    try:
        chart.base_chart._draw_curves(
            painter,
            QRectF(20.0, 20.0, 380.0, 320.0),
            page,
            dataset,
            (curve,),
            ranges,
        )
    finally:
        painter.end()

    dark_pixels = sum(
        1
        for y in range(20, 341)
        for x in range(20, 401)
        if image.pixelColor(x, y).lightness() < 170
    )
    assert dark_pixels >= 250


def test_extrema_preserving_print_rows_keeps_narrow_peaks_and_bounds_density() -> None:
    depth = np.linspace(100.0, 200.0, 10_001)
    values = np.zeros(depth.shape, dtype=np.float64)
    values[4321] = 100.0
    values[7654] = -80.0
    segment = np.arange(depth.size, dtype=np.int64)
    page = DepthPage(100.0, 200.0, 500, 360.0)
    rect = QRectF(0.0, 0.0, 300.0, 360.0)

    reduced = chart.base_chart._extrema_preserving_print_rows(
        segment,
        depth,
        values,
        page,
        rect,
    )

    assert 4321 in reduced
    assert 7654 in reduced
    assert 0 in reduced
    assert depth.size - 1 in reduced
    assert reduced.size < 1_000
    assert np.all(np.diff(reduced) > 0)


def test_extrema_preserving_print_rows_retains_missing_value_breaks() -> None:
    depth = np.linspace(100.0, 200.0, 10_001)
    values = np.sin(depth)
    values[4501:4504] = np.nan
    segment = np.arange(depth.size, dtype=np.int64)
    page = DepthPage(100.0, 200.0, 500, 360.0)
    rect = QRectF(0.0, 0.0, 300.0, 360.0)

    reduced = chart.base_chart._extrema_preserving_print_rows(
        segment,
        depth,
        values,
        page,
        rect,
    )

    retained_missing = reduced[~np.isfinite(values[reduced])]
    assert retained_missing.size >= 1
    assert retained_missing[0] >= 4501
    assert retained_missing[-1] <= 4503


def test_enhanced_chart_uses_compact_markers_not_text_callout_stack() -> None:
    source = Path(
        "src/geoworkbench/printing/hydrocarbon_interpretation_pdf_chart_enhanced.py"
    ).read_text(encoding="utf-8")

    assert "_draw_fluid_callouts" not in source
    assert "_fluid_callout_interval_text" not in source
    assert "_stagger_callout_centers" not in source
    assert "_draw_fluid_markers(" in source
    assert "fluid_marker_legend_specs" in source
    assert "marker_lane_offsets" in source
    assert "minimum_gap=badge_height + 1.0" in source
    assert "len(visible) <= 12" not in source
    assert "marker_lanes" in source
