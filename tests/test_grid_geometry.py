from __future__ import annotations

import pytest

from geoworkbench.tablet.grid_geometry import (
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
