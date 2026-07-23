from __future__ import annotations

import pytest

from geoworkbench.printing.pagination import (
    PrintPaginationSettings,
    PrintRangeMode,
    build_page_slices,
)


def test_selected_interval_uses_same_multipage_contract() -> None:
    pages = build_page_slices(
        pagination=PrintPaginationSettings(
            range_mode=PrintRangeMode.SELECTION,
            units_per_page=2.0,
            overlap=0.5,
        ),
        current_range=(0.0, 1.0),
        full_range=(0.0, 10.0),
        selection_range=(3.0, 7.0),
    )

    assert [(page.start, page.end) for page in pages] == [
        (3.0, 5.0),
        (4.5, 6.5),
        (6.0, 7.0),
    ]


def test_selected_interval_requires_a_selection() -> None:
    with pytest.raises(ValueError, match="интервал"):
        build_page_slices(
            pagination=PrintPaginationSettings(range_mode=PrintRangeMode.SELECTION),
            current_range=(0.0, 1.0),
            full_range=(0.0, 10.0),
        )


def test_single_sample_custom_range_produces_one_page() -> None:
    pages = build_page_slices(
        pagination=PrintPaginationSettings(
            range_mode=PrintRangeMode.CUSTOM,
            custom_start=1002.0,
            custom_end=1002.0,
        ),
        current_range=(1000.0, 1004.0),
        full_range=(1000.0, 1004.0),
    )

    assert [(page.start, page.end) for page in pages] == [(1002.0, 1002.0)]
