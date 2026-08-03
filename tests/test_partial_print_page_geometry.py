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
