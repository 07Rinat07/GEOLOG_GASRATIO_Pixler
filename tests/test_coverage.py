from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.services.coverage import (
    ChannelAvailability,
    CoverageSampleState,
    analyze_curve_coverage,
    analyze_dataset_coverage,
    classify_sample,
)


def make_dataset() -> Dataset:
    dataset = Dataset(
        "dataset",
        "Coverage",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0, 103.0]),
    )
    dataset.curves["gas"] = CurveData(
        CurveMetadata("gas", "TG", "TG", "%", "Total gas", dataset.dataset_id),
        np.array([0.0, np.nan, 2.5, np.inf]),
    )
    return dataset


def test_sample_states_do_not_conflate_zero_missing_and_unavailable() -> None:
    assert classify_sample(0.0) is CoverageSampleState.OBSERVED_ZERO
    assert classify_sample(-0.0) is CoverageSampleState.OBSERVED_ZERO
    assert classify_sample(1.0) is CoverageSampleState.OBSERVED_VALUE
    assert classify_sample(float("nan")) is CoverageSampleState.MISSING_SAMPLE
    assert classify_sample(float("inf")) is CoverageSampleState.MISSING_SAMPLE
    assert classify_sample(0.0, channel_available=False) is CoverageSampleState.CHANNEL_UNAVAILABLE


def test_curve_coverage_counts_observed_zero_and_missing() -> None:
    dataset = make_dataset()
    coverage = analyze_curve_coverage(dataset.curves["gas"], np.arange(4))

    assert coverage.availability is ChannelAvailability.AVAILABLE
    assert coverage.total_count == 4
    assert coverage.observed_count == 2
    assert coverage.zero_count == 1
    assert coverage.missing_count == 2
    assert coverage.unavailable_count == 0
    assert coverage.coverage_percent == 50.0
    assert coverage.zero_percent == 25.0
    assert coverage.zero_percent_of_observed == 50.0


def test_dataset_coverage_represents_missing_channel_as_unavailable() -> None:
    dataset = make_dataset()
    available, unavailable = analyze_dataset_coverage(
        dataset,
        ("gas",),
        np.array([0, 1, 2], dtype=np.int64),
        unavailable_mnemonics=("H2S",),
    )

    assert available.primary_state is CoverageSampleState.OBSERVED_VALUE
    assert unavailable.availability is ChannelAvailability.UNAVAILABLE
    assert unavailable.primary_state is CoverageSampleState.CHANNEL_UNAVAILABLE
    assert unavailable.total_count == 3
    assert unavailable.unavailable_count == 3
    assert unavailable.missing_count == 0
