from geoworkbench.printing.document_renderer import (
    PrintDocumentPage,
    PrintDocumentPlan,
    _page_target_content_height,
)
from geoworkbench.printing.pagination import PrintPageSlice
from geoworkbench.printing.print_layout import PrintContinuationSlice


def _page(start: float, end: float) -> PrintDocumentPage:
    return PrintDocumentPage(
        PrintPageSlice(start, end, 1, 1),
        PrintContinuationSlice(0.0, 100.0, 1, 1, 1.0),
        1,
        1,
    )


def test_full_automatic_page_keeps_canonical_viewport_height() -> None:
    plan = PrintDocumentPlan(
        (_page(0.0, 120.0),),
        target_content_height_px=6000,
        resolved_units_per_page=120.0,
    )

    assert _page_target_content_height(plan, plan.pages[0]) == 6000


def test_partial_last_page_shortens_only_its_viewport() -> None:
    page = _page(1945.9, 2016.2)
    plan = PrintDocumentPlan(
        (page,),
        target_content_height_px=6000,
        resolved_units_per_page=126.593,
    )

    assert _page_target_content_height(plan, page) == round(
        6000 * (2016.2 - 1945.9) / 126.593
    )


def test_repeated_bottom_header_reserves_space_without_narrowing_page() -> None:
    page = _page(1_951.58, 2_016.2)
    plan = PrintDocumentPlan(
        (page,),
        target_content_height_px=6000,
        resolved_units_per_page=89.444,
        tablet_header_height_px=1800,
    )

    target = _page_target_content_height(
        plan,
        page,
        repeat_column_header_at_bottom=True,
    )

    assert target is not None
    body = target - 1800
    canonical_body = 6000 - 1800
    assert body < round(canonical_body * (2_016.2 - 1_951.58) / 89.444)
    assert body + 1800 < canonical_body


def test_single_page_reserves_both_header_gaps() -> None:
    page = _page(1_469.38, 1_482.4)
    plan = PrintDocumentPlan(
        (page,),
        target_content_height_px=3000,
        resolved_units_per_page=89.444,
        tablet_header_height_px=900,
    )

    target = _page_target_content_height(
        plan,
        page,
        repeat_column_header_at_bottom=True,
    )

    assert target is not None
    assert target < 3000 - 900
