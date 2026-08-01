from PySide6.QtCore import QRectF

from geoworkbench.printing.hydrocarbon_interpretation_chart_front import (
    _chart_block,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_chart import (
    _readable_depth_ticks,
)
from geoworkbench.printing.hydrocarbon_interpretation_pdf_renderer import (
    DepthPage,
    chart_geometry,
    plan_depth_pages,
)


_LABELS = {
    "title": "Графики интерпретационных кривых по глубине",
    "note": "Печатная проверка графика.",
}


def test_print_chart_uses_dedicated_page_and_safe_width() -> None:
    html = _chart_block(
        "data:image/png;base64,AAAA",
        _LABELS,
        print_layout=True,
    )

    assert "page-break-before: always" in html
    assert "page-break-after: always" in html
    assert "page-break-inside: avoid" in html
    assert "width: 86%" in html
    assert "max-width: 880px" in html


def test_preview_chart_remains_responsive_without_forced_page_break() -> None:
    html = _chart_block(
        "data:image/png;base64,AAAA",
        _LABELS,
        print_layout=False,
    )
    compact_html = "".join(html.split())

    assert "page-break-before:always" not in compact_html
    assert "page-break-after:always" not in compact_html
    assert "width:100%" in compact_html
    assert "max-width:1050px" in compact_html


def test_short_well_uses_one_page_without_vertical_stretching() -> None:
    available_height = 330.0

    pages = plan_depth_pages(1_000.0, 1_010.0, available_height)

    assert len(pages) == 1
    assert pages[0].top_depth == 1_000.0
    assert pages[0].bottom_depth == 1_010.0
    assert 0.0 < pages[0].plot_height_points < available_height


def test_long_well_is_split_into_continuous_readable_pages() -> None:
    pages = plan_depth_pages(1_000.0, 4_000.0, 330.0)

    assert 2 <= len(pages) <= 12
    assert pages[0].top_depth == 1_000.0
    assert pages[-1].bottom_depth == 4_000.0
    assert len({page.scale_denominator for page in pages}) == 1
    assert all(page.plot_height_points <= 330.0 + 1e-6 for page in pages)
    assert all(
        abs(left.bottom_depth - right.top_depth) < 1e-9
        for left, right in zip(pages, pages[1:], strict=False)
    )


def test_large_well_uses_coarser_scale_than_small_well() -> None:
    short = plan_depth_pages(1_000.0, 1_050.0, 330.0)
    long = plan_depth_pages(1_000.0, 4_000.0, 330.0)

    assert short[0].scale_denominator < long[0].scale_denominator


def test_axis_keeps_exact_page_limits_without_overlapping_nearby_round_labels() -> None:
    first_page = DepthPage(1_000.0, 1_253.7, 2_000, 330.0)
    last_page = DepthPage(3_790.3, 4_000.0, 2_000, 273.0)

    first_ticks = _readable_depth_ticks(first_page, 50.0, 330.0)
    last_ticks = _readable_depth_ticks(last_page, 50.0, 273.0)

    assert first_ticks[0] == first_page.top_depth
    assert first_ticks[-1] == first_page.bottom_depth
    assert 1_250.0 not in first_ticks
    assert last_ticks[0] == last_page.top_depth
    assert last_ticks[-1] == last_page.bottom_depth
    assert 3_800.0 not in last_ticks


def test_chart_geometry_keeps_both_depth_scales_and_tracks_inside_page() -> None:
    page_rect = QRectF(40.0, 40.0, 760.0, 500.0)
    page = plan_depth_pages(1_000.0, 1_120.0, 330.0)[0]

    geometry = chart_geometry(page_rect, page, panel_count=3)

    rectangles = (
        geometry.left_axis_rect,
        geometry.right_axis_rect,
        *geometry.panel_rects,
        geometry.legend_rect,
        geometry.note_rect,
    )
    assert all(rect.left() >= page_rect.left() - 1e-6 for rect in rectangles)
    assert all(rect.right() <= page_rect.right() + 1e-6 for rect in rectangles)
    assert all(rect.top() >= page_rect.top() - 1e-6 for rect in rectangles)
    assert all(rect.bottom() <= page_rect.bottom() + 1e-6 for rect in rectangles)
    assert geometry.left_axis_rect.right() < geometry.panel_rects[0].left()
    assert geometry.panel_rects[-1].right() < geometry.right_axis_rect.left()
    assert geometry.left_axis_rect.height() == geometry.right_axis_rect.height()
    assert all(rect.height() == geometry.left_axis_rect.height() for rect in geometry.panel_rects)
