from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.calculations.opus_gasomer import (
    OPUS_GASOMER_INDICATORS,
    OPUS_GASOMER_LEGACY_MAX_MODE,
    OPUS_GASOMER_SYNCHRONOUS_MODE,
    aggregate_opus_gasomer_interval,
    calculate_opus_gasomer_batch,
    calculate_opus_gasomer_legacy_max_interval,
)


INPUT_NAMES = ("C1", "C2", "C3", "C4", "C5", "TOTAL_GAS")
LOD = {name: 1.0e-6 for name in INPUT_NAMES}


def _inputs(rows: list[tuple[float, float, float, float, float, float]]) -> dict[str, np.ndarray]:
    return {
        name: np.array([row[index] for row in rows], dtype=np.float64)
        for index, name in enumerate(INPUT_NAMES)
    }


def test_interval_aggregates_unique_support_from_synchronous_rows() -> None:
    depth = np.array([1000.0, 1000.2, 1000.4, 1000.6])
    batch = calculate_opus_gasomer_batch(
        _inputs(
            [
                (3.0, 2.0, 1.0, 1.0, 1.0, 9.0),
                (9.0, 0.5, 0.1, 0.05, 0.02, 10.0),
                (0.5, 0.3, 0.2, 0.1, 0.05, 2.0),
                (1.0, 1.0, 1.0, 1.0, 1.0, 5.0),
            ]
        ),
        lod=LOD,
    )
    assert batch.row_class_codes.tolist() == [2, 4, 2, 1]

    interval = aggregate_opus_gasomer_interval(
        depth,
        batch,
        top_depth=1000.0,
        bottom_depth=1000.4,
    )

    assert interval.calculation_mode == OPUS_GASOMER_SYNCHRONOUS_MODE
    assert interval.total_rows == interval.valid_rows == 3
    assert interval.class_code == 2
    assert interval.support_fraction == pytest.approx(2.0 / 3.0)
    assert interval.class_counts == {1: 0, 2: 2, 3: 0, 4: 1, 5: 0, 6: 0}
    assert interval.indicator_available_counts == {
        name: 3 for name in OPUS_GASOMER_INDICATORS
    }
    assert not interval.warnings


def test_interval_tie_remains_undefined() -> None:
    depth = np.array([1000.0, 1000.2])
    batch = calculate_opus_gasomer_batch(
        _inputs(
            [
                (3.0, 2.0, 1.0, 1.0, 1.0, 9.0),
                (9.0, 0.5, 0.1, 0.05, 0.02, 10.0),
            ]
        ),
        lod=LOD,
    )

    interval = aggregate_opus_gasomer_interval(
        depth,
        batch,
        top_depth=1000.0,
        bottom_depth=1000.2,
    )

    assert batch.row_class_codes.tolist() == [2, 4]
    assert interval.class_code == 7
    assert interval.support_fraction == 0.5
    assert "Interval row-class support is tied" in interval.warnings


def test_interval_keeps_indicator_qc_distribution() -> None:
    depth = np.array([10.0, 10.2, 10.4])
    inputs = _inputs(
        [
            (0.30, 0.20, 0.10, 0.08, 0.04, 1.0),
            (0.30, 0.20, 0.10, 0.08, np.nan, 1.0),
            (0.30, 0.20, 0.10, 0.005, 0.04, 1.0),
        ]
    )
    lod = {name: 0.01 for name in INPUT_NAMES}
    batch = calculate_opus_gasomer_batch(inputs, lod=lod)

    interval = aggregate_opus_gasomer_interval(
        depth,
        batch,
        top_depth=10.0,
        bottom_depth=10.4,
    )

    assert interval.indicator_available_counts["OPUS_GM_1"] == 3
    assert interval.indicator_available_counts["OPUS_GM_2"] == 2
    assert interval.indicator_available_counts["OPUS_GM_4"] == 1
    assert interval.indicator_state_counts["OPUS_GM_4"]["missing"] == 1
    assert interval.indicator_state_counts["OPUS_GM_4"]["below_lod"] == 1
    assert sum(interval.indicator_vote_counts["OPUS_GM_4"].values()) == 3


def test_legacy_max_is_explicit_and_exposes_synthetic_composition() -> None:
    depth = np.array([1000.0, 1000.2])
    inputs = _inputs(
        [
            (9.0, 0.5, 0.1, 0.05, 0.02, 10.0),
            (0.5, 3.0, 2.0, 1.0, 1.0, 10.0),
        ]
    )
    synchronous = calculate_opus_gasomer_batch(inputs, lod=LOD)
    interval = aggregate_opus_gasomer_interval(
        depth,
        synchronous,
        top_depth=1000.0,
        bottom_depth=1000.2,
    )
    legacy = calculate_opus_gasomer_legacy_max_interval(
        depth,
        inputs,
        top_depth=1000.0,
        bottom_depth=1000.2,
        maximum_span=0.2,
        lod=LOD,
    )

    assert synchronous.row_class_codes.tolist() == [4, 1]
    assert interval.class_code == 7
    assert legacy.calculation_mode == OPUS_GASOMER_LEGACY_MAX_MODE
    assert legacy.synthetic_composition is True
    assert legacy.source_depths["C1"] == 1000.0
    assert legacy.source_depths["C2"] == 1000.2
    assert "Legacy MAX combines component maxima from different depths" in legacy.warnings
    assert int(legacy.batch.row_class_codes[0]) == 1
    legacy_vector = np.array(
        [legacy.batch.indicators[name].values[0] for name in OPUS_GASOMER_INDICATORS]
    )
    synchronous_vectors = np.column_stack(
        [synchronous.indicators[name].values for name in OPUS_GASOMER_INDICATORS]
    )
    assert not any(np.allclose(legacy_vector, row) for row in synchronous_vectors)


def test_legacy_max_requires_explicit_short_interval_limit() -> None:
    depth = np.array([1000.0, 1001.0])
    inputs = _inputs(
        [
            (3.0, 2.0, 1.0, 1.0, 1.0, 9.0),
            (4.0, 2.0, 1.0, 1.0, 1.0, 10.0),
        ]
    )

    with pytest.raises(ValueError, match="шире"):
        calculate_opus_gasomer_legacy_max_interval(
            depth,
            inputs,
            top_depth=1000.0,
            bottom_depth=1001.0,
            maximum_span=0.5,
            lod=LOD,
        )
    with pytest.raises(ValueError, match="положительным"):
        calculate_opus_gasomer_legacy_max_interval(
            depth,
            inputs,
            top_depth=1000.0,
            bottom_depth=1001.0,
            maximum_span=0.0,
            lod=LOD,
        )


def test_interval_without_depth_rows_is_rejected() -> None:
    depth = np.array([1000.0, 1000.2])
    batch = calculate_opus_gasomer_batch(
        _inputs(
            [
                (3.0, 2.0, 1.0, 1.0, 1.0, 9.0),
                (4.0, 2.0, 1.0, 1.0, 1.0, 10.0),
            ]
        ),
        lod=LOD,
    )

    with pytest.raises(ValueError, match="нет глубинных строк"):
        aggregate_opus_gasomer_interval(
            depth,
            batch,
            top_depth=2000.0,
            bottom_depth=2001.0,
        )
