from dataclasses import dataclass

import pytest

from geoworkbench.services.interval_overlap_index import IntervalOverlapIndex


@dataclass
class Interval:
    name: str
    top_depth: float
    bottom_depth: float


def test_interval_overlap_index_preserves_inclusive_masterlog_boundaries() -> None:
    items = [
        Interval("a", 0.0, 10.0),
        Interval("b", 5.0, 6.0),
        Interval("c", 20.0, 30.0),
        Interval("d", 30.0, 40.0),
    ]
    index = IntervalOverlapIndex.build(items)

    assert [item.name for item in index.overlapping(10.0, 20.0)] == ["a", "c"]
    assert [item.name for item in index.overlapping(30.0, 30.0)] == ["c", "d"]


def test_interval_overlap_index_handles_long_running_interval_before_page() -> None:
    items = [
        Interval("long", 0.0, 100.0),
        Interval("short-before", 10.0, 11.0),
        Interval("visible", 50.0, 55.0),
        Interval("after", 70.0, 80.0),
    ]
    index = IntervalOverlapIndex.build(items)

    assert [item.name for item in index.overlapping(49.0, 60.0)] == [
        "long",
        "visible",
    ]


def test_interval_overlap_index_returns_sorted_immutable_snapshot() -> None:
    items = [
        Interval("late", 20.0, 25.0),
        Interval("early", 5.0, 10.0),
    ]
    index = IntervalOverlapIndex.build(items)
    items.clear()

    assert [item.name for item in index.items] == ["early", "late"]
    assert [item.name for item in index.overlapping(0.0, 30.0)] == ["early", "late"]


def test_interval_overlap_index_rejects_reversed_query() -> None:
    index = IntervalOverlapIndex.build([Interval("a", 0.0, 1.0)])

    with pytest.raises(ValueError):
        index.overlapping(2.0, 1.0)
