from __future__ import annotations

import numpy as np

from geoworkbench.services.dexp_gap_repair import repair_dexp_short_gaps


def test_repair_dexp_short_gaps_interpolates_bounded_internal_interval() -> None:
    depth = np.arange(1_000.0, 1_010.0)
    values = np.array([1.0, 1.1, np.nan, np.nan, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9])

    result = repair_dexp_short_gaps(depth, values, depth_unit="m")

    assert result.repaired_points == 2
    assert result.repaired_gaps == 1
    assert result.remaining_missing_points == 0
    assert np.allclose(result.values[2:4], [1.2, 1.3])
    assert np.array_equal(
        result.repaired_mask,
        [False, False, True, True, False, False, False, False, False, False],
    )
    assert np.isnan(values[2])


def test_repair_dexp_short_gaps_preserves_edges_and_long_intervals() -> None:
    depth = np.arange(0.0, 16.0)
    values = np.array(
        [
            np.nan,
            1.0,
            1.1,
            np.nan,
            np.nan,
            np.nan,
            np.nan,
            np.nan,
            np.nan,
            np.nan,
            1.9,
            2.0,
            2.1,
            2.2,
            2.3,
            np.nan,
        ]
    )

    result = repair_dexp_short_gaps(depth, values, depth_unit="m")

    assert result.repaired_points == 0
    assert result.repaired_gaps == 0
    assert result.remaining_missing_points == 9
    assert np.isnan(result.values[0])
    assert np.all(np.isnan(result.values[3:10]))
    assert np.isnan(result.values[-1])


def test_repair_dexp_short_gaps_rejects_nonpositive_anchors() -> None:
    depth = np.arange(5.0)
    values = np.array([1.0, 0.0, np.nan, 1.2, 1.3])

    result = repair_dexp_short_gaps(depth, values, depth_unit="m")

    assert result.repaired_points == 0
    assert np.isnan(result.values[2])


def test_repair_dexp_short_gaps_supports_descending_depth() -> None:
    depth = np.array([100.0, 99.0, 98.0, 97.0, 96.0])
    values = np.array([1.0, np.nan, np.nan, 1.6, 1.8])

    result = repair_dexp_short_gaps(depth, values, depth_unit="m")

    assert result.repaired_points == 2
    assert np.allclose(result.values[1:3], [1.2, 1.4])


def test_repair_dexp_short_gaps_preserves_rotary_slide_boundary() -> None:
    depth = np.arange(5.0)
    values = np.array([1.0, np.nan, np.nan, 1.6, 1.8])
    modes = np.array([1, 1, 2, 2, 2], dtype=np.int16)

    result = repair_dexp_short_gaps(
        depth,
        values,
        depth_unit="m",
        segment_labels=modes,
        repairable_mask=np.ones(5, dtype=bool),
    )

    assert result.repaired_points == 0
    assert np.all(np.isnan(result.values[1:3]))


def test_repair_dexp_short_gaps_preserves_slide_without_bit_rpm() -> None:
    depth = np.arange(5.0)
    values = np.array([1.0, np.nan, np.nan, 1.6, 1.8])
    modes = np.full(5, 2, dtype=np.int16)
    repairable = np.array([True, False, False, True, True])

    result = repair_dexp_short_gaps(
        depth,
        values,
        depth_unit="m",
        segment_labels=modes,
        repairable_mask=repairable,
    )

    assert result.repaired_points == 0
    assert np.all(np.isnan(result.values[1:3]))
