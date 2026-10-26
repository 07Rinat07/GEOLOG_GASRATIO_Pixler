from types import SimpleNamespace

from geoworkbench.printing.document_renderer import (
    PrintDocumentPage,
    PrintDocumentPlan,
    _page_target_content_height,
    _selected_tablet_print_header_height,
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


def test_selected_print_header_ignores_merged_screen_title_height() -> None:
    # A geology heading absorbs the on-screen curve band of unselected tracks.
    # Pagination must use its natural height, not the merged 200px QLabel.
    geology = SimpleNamespace(
        widget=SimpleNamespace(
            natural_title_header_height=96,
            print_curve_header_height=0,
            title=SimpleNamespace(height=lambda: 200),
        )
    )
    assert _selected_tablet_print_header_height((geology,)) == 96


def test_selected_print_header_synchronizes_title_and_curve_bands_separately() -> None:
    geology = SimpleNamespace(
        widget=SimpleNamespace(
            natural_title_header_height=96,
            print_curve_header_height=0,
        )
    )
    curve = SimpleNamespace(
        widget=SimpleNamespace(
            natural_title_header_height=36,
            print_curve_header_height=72,
        )
    )
    # Print capture aligns both bands across the selected tracks: 96 + 72.
    assert _selected_tablet_print_header_height((geology, curve)) == 168
    assert _selected_tablet_print_header_height((curve,)) == 108
