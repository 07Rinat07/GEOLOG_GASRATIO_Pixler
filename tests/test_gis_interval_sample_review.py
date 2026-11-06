from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.services.gis_interval_sample_review import review_gis_interval_samples
from test_gis_reference_input_review import _dataset


def review(dataset, top=100, bottom=102):
    return review_gis_interval_samples(
        dataset, method_id="igr-linear-1", curve_key="selected",
        top_md_m=top, bottom_md_m=bottom,
    )


def test_counts_actual_rows_and_missing_without_mutating_source():
    dataset = _dataset()
    values = dataset.curves["selected"].values
    values[0] = 0.0
    result = review(dataset)
    assert (result.sample_count, result.finite_count, result.missing_count) == (3, 2, 1)
    assert result.finite_md_bounds == (100.0, 102.0)
    assert result.source.curve.source_dataset_id == "original-run"
    np.testing.assert_equal(values, [0.0, np.nan, 30.0])
    missing = review(dataset, 100.5, 101.5)
    assert (missing.sample_count, missing.finite_count, missing.missing_count) == (1, 0, 1)
    assert missing.finite_md_bounds is None
    assert review(dataset, 110, 120).sample_count == 0


def test_descending_axis_and_stale_unit_are_handled_explicitly():
    dataset = _dataset()
    dataset.active_index.values = np.array([102.0, 101.0, 100.0])
    assert review(dataset).finite_md_bounds == (100.0, 102.0)
    curve = dataset.curves["selected"]
    curve.metadata = replace(curve.metadata, unit="unknown")
    with pytest.raises(ValueError, match="source review failed"):
        review(dataset)


@pytest.mark.parametrize("top,bottom", [(True, 102), (100, np.inf), (102, 100), (100, 100), ("100", 102)])
def test_invalid_interval_is_rejected(top, bottom):
    with pytest.raises(ValueError, match="Interval bounds"):
        review(_dataset(), top, bottom)
