from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.calculations.curve_continuity import build_segment_connect_mask
from geoworkbench.tablet.geometry_cache import (
    CurveGeometryCache,
    CurveGeometryKey,
    is_derived_gas_curve_id,
)


@pytest.mark.parametrize(
    "mnemonic",
    (
        "PIXLER_C1_C2",
        "C1_C2",
        "C1_C4",
        "WH",
        "WETNESS",
        "IC4_NC4",
        "C2_REL",
        "TG_NORM",
    ),
)
def test_all_derived_gas_aliases_use_sparse_update_continuity(
    mnemonic: str,
) -> None:
    assert is_derived_gas_curve_id(mnemonic)


def test_raw_component_is_not_misclassified_as_derived() -> None:
    assert not is_derived_gas_curve_id("C1")


def test_pixler_sparse_updates_form_lines_but_keep_long_outage() -> None:
    depth = np.arange(1703.0, 1753.5, 0.5, dtype=np.float64)
    values = np.full(depth.shape, np.nan, dtype=np.float64)
    for sample_depth, sample_value in (
        (1705.0, 3.0),
        (1710.0, 3.5),
        (1715.0, 4.0),
        (1745.0, 5.0),
        (1750.0, 5.5),
    ):
        values[np.flatnonzero(np.isclose(depth, sample_depth))[0]] = sample_value

    key = CurveGeometryKey(
        curve_id="PIXLER_C1_C2",
        axis_id="depth",
        values_revision="values-1",
        axis_revision="axis-1",
        top=1703.28,
        bottom=1753.28,
        max_points=5000,
        positive_values_only=False,
    )
    sampled_values, sampled_depth = CurveGeometryCache().get_or_build(
        key, depth, values
    )
    connect = build_segment_connect_mask(sampled_depth, sampled_values)

    finite_depth = sampled_depth[np.isfinite(sampled_values)]
    assert np.allclose(
        finite_depth,
        np.asarray([1705.0, 1710.0, 1715.0, 1745.0, 1750.0]),
    )
    assert np.count_nonzero(connect) == 3
    separator = np.flatnonzero(~np.isfinite(sampled_values))
    assert separator.size == 1
    assert 1715.0 < sampled_depth[separator[0]] < 1745.0
