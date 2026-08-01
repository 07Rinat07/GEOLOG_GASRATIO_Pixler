from __future__ import annotations

import pytest

from geoworkbench.tablet.grid_geometry import (
    DEFAULT_DEPTH_GRID_MAJOR_STEP,
    DEFAULT_GRID_ALPHA,
    DEFAULT_GRID_MAJOR_DIVISIONS,
    DEFAULT_GRID_MINOR_DIVISIONS,
    adaptive_aligned_step,
    aligned_engineering_grid_lines,
    engineering_tick_levels,
    normalized_grid_lines,
    project_grid_lines,
)


def test_grid_geometry_is_qt_independent_and_projects_units() -> None:
    assert engineering_tick_levels(1000.0, 1100.0, 4, 10) == (
        (25.0, 1000.0),
        (2.5, 1000.0),
    )
    assert project_grid_lines(100.0, 2, 2, origin=10.0) == (
        (10.0, True),
        (35.0, False),
        (60.0, True),
        (85.0, False),
        (110.0, True),
    )
    assert [line.fraction for line in normalized_grid_lines(2, 2)] == [
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
    ]


def test_grid_projection_rejects_invalid_geometry() -> None:
    with pytest.raises(ValueError):
        project_grid_lines(-1.0, 5, 5)


def test_grid_defaults_define_one_shared_engineering_contract() -> None:
    assert DEFAULT_GRID_MAJOR_DIVISIONS == 5
    assert DEFAULT_GRID_MINOR_DIVISIONS == 5
    assert DEFAULT_GRID_ALPHA == 0.2
    assert DEFAULT_DEPTH_GRID_MAJOR_STEP == 5.0


def test_adaptive_depth_step_uses_one_two_five_engineering_series() -> None:
    assert adaptive_aligned_step(47.0, 97.0) == 5.0
    assert adaptive_aligned_step(0.0, 250.0) == 20.0
    assert adaptive_aligned_step(0.0, 2_000.0) == 100.0


def test_aligned_depth_grid_contains_major_and_minor_lines() -> None:
    lines = aligned_engineering_grid_lines(47.0, 62.0, 5.0, 5)

    assert [line.value for line in lines if line.major] == [50.0, 55.0, 60.0]
    assert [line.value for line in lines if not line.major] == [
        47.0,
        48.0,
        49.0,
        51.0,
        52.0,
        53.0,
        54.0,
        56.0,
        57.0,
        58.0,
        59.0,
        61.0,
        62.0,
    ]
