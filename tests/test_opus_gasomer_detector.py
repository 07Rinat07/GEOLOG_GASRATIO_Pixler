from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.calculations.opus_gasomer import (
    OpusGasomerDetectorPolicy,
    OpusGasomerValueState,
    detect_opus_gasomer_intervals,
    load_opus_gasomer_detector_policy,
)


def _policy() -> OpusGasomerDetectorPolicy:
    return OpusGasomerDetectorPolicy(
        smoothing_span=0.4,
        background_half_span=5.0,
        peak_exclusion_z=3.5,
        robust_scale_factor=1.4826,
        robust_z_threshold=3.0,
        minimum_delta_lod_multiple=3.0,
        minimum_contrast=3.0,
        maximum_candidate_separation=0.4,
        minimum_interval_span=0.4,
        minimum_candidate_samples=3,
        low_background_warning_percent=0.1,
    )


def test_versioned_detector_policy_is_loaded_from_profile() -> None:
    policy = load_opus_gasomer_detector_policy()

    assert policy.smoothing_span == 1.0
    assert policy.background_half_span == 10.0
    assert policy.robust_z_threshold == 3.0
    assert policy.minimum_delta_lod_multiple == 3.0
    assert policy.minimum_contrast == 3.0
    assert policy.low_background_warning_percent == 0.1


def test_contrast_show_below_point_one_percent_is_retained_with_warning() -> None:
    depth = np.arange(0.0, 40.0, 0.2)
    total_gas = np.full(depth.shape, 0.0001)
    total_gas[50:55] = 0.01

    result = detect_opus_gasomer_intervals(
        depth,
        total_gas,
        total_gas_lod=0.0001,
        policy=_policy(),
    )

    assert len(result.intervals) == 1
    interval = result.intervals[0]
    assert interval.background_median == pytest.approx(0.0001)
    assert interval.peak_total_gas == pytest.approx(0.01)
    assert interval.delta_peak > 0.009
    assert interval.max_robust_z > 3.0
    assert interval.max_contrast >= 100.0
    assert interval.low_background_warning is True
    assert result.candidate_mask.any()
    assert any("not a hard gate" in warning for warning in result.warnings)


def test_local_background_shift_does_not_hide_later_show() -> None:
    depth = np.arange(0.0, 100.0, 0.2)
    total_gas = np.where(depth < 50.0, 0.01, 0.10)
    total_gas[100:105] = 0.05
    total_gas[350:355] = 0.50

    result = detect_opus_gasomer_intervals(
        depth,
        total_gas,
        total_gas_lod=0.001,
        policy=_policy(),
    )

    assert len(result.intervals) == 2
    first, second = result.intervals
    assert first.top_depth <= 20.0 <= first.bottom_depth
    assert second.top_depth <= 70.0 <= second.bottom_depth
    assert first.background_median == pytest.approx(0.01)
    assert second.background_median == pytest.approx(0.10)
    assert first.max_contrast == pytest.approx(5.0)
    assert second.max_contrast == pytest.approx(5.0)


def test_flat_low_background_does_not_create_false_interval() -> None:
    depth = np.arange(0.0, 20.0, 0.2)
    total_gas = np.full(depth.shape, 0.0001)

    result = detect_opus_gasomer_intervals(
        depth,
        total_gas,
        total_gas_lod=0.0001,
        policy=_policy(),
    )

    assert not result.raw_candidate_mask.any()
    assert not result.candidate_mask.any()
    assert result.intervals == ()


def test_ppm_and_percent_detection_are_identical() -> None:
    depth = np.arange(0.0, 40.0, 0.2)
    percent_values = np.full(depth.shape, 0.01)
    percent_values[50:55] = 0.05

    percent = detect_opus_gasomer_intervals(
        depth,
        percent_values,
        unit="%vol",
        total_gas_lod=0.001,
        policy=_policy(),
    )
    ppm = detect_opus_gasomer_intervals(
        depth,
        percent_values * 10_000.0,
        unit="ppm",
        total_gas_lod=10.0,
        policy=_policy(),
    )

    for name in (
        "total_gas_percent",
        "smoothed_total_gas",
        "local_background",
        "local_robust_scale",
        "delta_total_gas",
        "robust_z",
        "contrast",
    ):
        np.testing.assert_allclose(
            getattr(percent, name),
            getattr(ppm, name),
            rtol=2e-14,
            equal_nan=True,
        )
    np.testing.assert_array_equal(percent.candidate_mask, ppm.candidate_mask)
    assert percent.intervals == ppm.intervals


def test_descending_depth_preserves_source_order_and_interval_depths() -> None:
    depth = np.arange(0.0, 40.0, 0.2)
    total_gas = np.full(depth.shape, 0.01)
    total_gas[50:55] = 0.05
    ascending = detect_opus_gasomer_intervals(
        depth,
        total_gas,
        total_gas_lod=0.001,
        policy=_policy(),
    )
    descending = detect_opus_gasomer_intervals(
        depth[::-1],
        total_gas[::-1],
        total_gas_lod=0.001,
        policy=_policy(),
    )

    np.testing.assert_allclose(
        ascending.local_background,
        descending.local_background[::-1],
        equal_nan=True,
    )
    np.testing.assert_array_equal(
        ascending.candidate_mask,
        descending.candidate_mask[::-1],
    )
    assert ascending.intervals == descending.intervals


def test_regular_fast_path_is_physical_and_irregular_fallback_retains_event() -> None:
    regular_depth = np.arange(0.0, 60.0, 0.2)
    irregular_depth = regular_depth.copy()
    irregular_depth[200:] += 0.01
    total_gas = np.full(regular_depth.shape, 0.01)
    total_gas[50:55] = 0.05

    regular = detect_opus_gasomer_intervals(
        regular_depth,
        total_gas,
        total_gas_lod=0.001,
        policy=_policy(),
    )
    irregular = detect_opus_gasomer_intervals(
        irregular_depth,
        total_gas,
        total_gas_lod=0.001,
        policy=_policy(),
    )

    np.testing.assert_array_equal(np.flatnonzero(regular.candidate_mask), np.arange(50, 55))
    assert len(regular.intervals) == len(irregular.intervals) == 1
    regular_interval = regular.intervals[0]
    irregular_interval = irregular.intervals[0]
    assert regular_interval.top_depth == irregular_interval.top_depth == 10.0
    assert regular_interval.bottom_depth == 10.8
    assert irregular_interval.bottom_depth >= regular_interval.bottom_depth
    assert regular_interval.background_median == irregular_interval.background_median == 0.01
    assert regular_interval.peak_total_gas == irregular_interval.peak_total_gas == 0.05
    assert regular_interval.max_contrast == irregular_interval.max_contrast == 5.0


@pytest.mark.parametrize(
    ("lod", "message"),
    (
        (0.0, "положительным"),
        (float("nan"), "положительным"),
    ),
)
def test_detector_requires_explicit_positive_total_gas_lod(
    lod: float,
    message: str,
) -> None:
    depth = np.array([0.0, 0.2])
    total_gas = np.array([0.01, 0.02])

    with pytest.raises(ValueError, match=message):
        detect_opus_gasomer_intervals(
            depth,
            total_gas,
            total_gas_lod=lod,
            policy=_policy(),
        )


def test_missing_and_invalid_total_gas_keep_distinct_states() -> None:
    depth = np.arange(0.0, 2.0, 0.2)
    total_gas = np.full(depth.shape, 0.01)
    total_gas[2] = np.nan
    total_gas[4] = -1.0

    result = detect_opus_gasomer_intervals(
        depth,
        total_gas,
        total_gas_lod=0.001,
        policy=_policy(),
    )

    assert result.input_states[2] == int(OpusGasomerValueState.MISSING)
    assert result.input_states[4] == int(OpusGasomerValueState.INVALID)
    assert not result.raw_candidate_mask[[2, 4]].any()
