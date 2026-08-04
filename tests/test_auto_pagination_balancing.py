from __future__ import annotations

import pytest

from geoworkbench.printing.auto_pagination import balanced_automatic_page_ranges
from geoworkbench.printing.pagination import MAX_PRINT_PAGE_COUNT


def test_tiny_bl_data_tail_is_merged_into_balanced_regular_pages() -> None:
    ranges = balanced_automatic_page_ranges(
        1174.8,
        1482.4,
        first_units_per_page=51.75,
        regular_units_per_page=127.46,
    )

    assert len(ranges) == 3
    assert ranges[0] == pytest.approx((1174.8, 1226.55))
    assert ranges[-1][1] == pytest.approx(1482.4)
    regular_spans = [end - start for start, end in ranges[1:]]
    assert regular_spans[0] == pytest.approx(regular_spans[1])
    assert min(regular_spans) > 120.0


def test_normal_partial_final_page_is_not_rebalanced() -> None:
    ranges = balanced_automatic_page_ranges(
        0.0,
        250.0,
        first_units_per_page=60.0,
        regular_units_per_page=100.0,
    )

    assert ranges == ((0.0, 60.0), (60.0, 160.0), (160.0, 250.0))


def test_short_real_gas_tail_is_absorbed_without_an_extra_page() -> None:
    ranges = balanced_automatic_page_ranges(
        47.0,
        2016.2,
        first_units_per_page=25.5714,
        regular_units_per_page=92.0,
    )

    assert len(ranges) == 22
    assert ranges[-1][1] == pytest.approx(2016.2)
    regular_spans = [end - start for start, end in ranges[1:]]
    assert max(regular_spans) < 92.0 * 1.03
    assert regular_spans == pytest.approx([regular_spans[0]] * len(regular_spans))


def test_rebalancing_never_exceeds_three_percent_density_change() -> None:
    ranges = balanced_automatic_page_ranges(
        0.0,
        272.0,
        first_units_per_page=50.0,
        regular_units_per_page=100.0,
    )

    assert ranges == ((0.0, 50.0), (50.0, 150.0), (150.0, 250.0), (250.0, 272.0))


def test_excessive_automatic_page_count_is_rejected_before_looping() -> None:
    with pytest.raises(ValueError, match="безопасный предел"):
        balanced_automatic_page_ranges(
            0.0,
            float(MAX_PRINT_PAGE_COUNT + 1),
            first_units_per_page=1.0,
            regular_units_per_page=1.0,
        )
