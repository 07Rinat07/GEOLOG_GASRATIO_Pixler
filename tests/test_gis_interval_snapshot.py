from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.services.gis_interval_sample_review import (
    GisIntervalReviewCancelled, review_gis_source_interval_batch,
)
from geoworkbench.services.gis_interval_snapshot import GisIntervalSnapshot
from test_gis_interval_compare import _two_curves


def test_snapshot_copies_selected_arrays_and_preserves_source_review():
    source = _two_curves()
    snapshot = GisIntervalSnapshot(source, ("RT",), lambda: False)
    assert snapshot.dataset is not source
    assert snapshot.dataset.active_index.values is not source.active_index.values
    assert snapshot.dataset.curves["RT"].values is not source.curves["RT"].values
    assert snapshot.dataset.curves["GR"].values.size == 0
    item, = review_gis_source_interval_batch(
        snapshot.dataset, curve_keys=("RT",), top_md_m=100, bottom_md_m=102,
    )
    assert item.review is not None and item.review.finite_value_bounds == (0.0, 20.0)
    assert snapshot.matches(lambda: False)
    np.testing.assert_equal(source.curves["RT"].values, [0.0, 20.0, np.nan])


@pytest.mark.parametrize("change", ["values", "axis_values", "unit", "version", "manifest", "replacement"])
def test_snapshot_rejects_source_edits_including_inplace_changes(change):
    source = _two_curves()
    snapshot = GisIntervalSnapshot(source, ("RT",), lambda: False)
    if change == "values":
        source.curves["RT"].values[0] = 9.0
    elif change == "axis_values":
        source.active_index.values[0] = 99.0
    elif change == "unit":
        source.curves["RT"].metadata = replace(source.curves["RT"].metadata, unit="changed")
    elif change == "version":
        source.curves["RT"].version += 1
    elif change == "manifest":
        source.parameters["changed"] = "yes"
    else:
        source.curves["RT"].values = source.curves["RT"].values.copy()
    assert not snapshot.matches(lambda: False)


def test_progress_and_cooperative_cancellation_do_not_return_partial_results():
    source = _two_curves()
    progress = []

    def on_progress(done, total):
        progress.append((done, total))

    with pytest.raises(GisIntervalReviewCancelled):
        review_gis_source_interval_batch(
            source, curve_keys=("GR", "RT"), top_md_m=100, bottom_md_m=102,
            progress=on_progress, cancelled=lambda: bool(progress),
        )
    assert progress == [(1, 2)]


def test_cancel_during_snapshot_is_explicit():
    with pytest.raises(GisIntervalReviewCancelled):
        GisIntervalSnapshot(_two_curves(), ("GR",), lambda: True)
