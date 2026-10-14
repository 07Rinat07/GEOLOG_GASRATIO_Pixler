"""Acceptance tests for source-exact VALUE markers over sparse mud-gas samples."""

import numpy as np
import pytest

from geoworkbench.domain.models import (
    Dataset, DatasetIndex, DatasetKind, DepthDomain, IndexRole, IndexType,
)
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


@pytest.mark.parametrize("use_time", [False, True])
def test_empty_track_picker_omits_missing_channel_without_substituting_neighbor(
    qapp, use_time,
):
    depth = np.array([100.0, 100.0, 101.0]) if use_time else np.array([100.0, 101.0, 102.0])
    dataset = Dataset("sparse-flags", "Sparse flags", DatasetKind.GTI, DepthDomain.MD, depth)
    if use_time:
        dataset.add_index(DatasetIndex(
            "time", "TIME", IndexType.RELATIVE_TIME, IndexRole.TIME, "s",
            np.array([0.0, 60.0, 120.0]),
        ))
    dataset.upsert_curve("TG", np.array([10.0, 20.0, 30.0]), unit="%")
    dataset.upsert_curve("C1", np.array([2.0, np.nan, 4.0]), unit="%")
    dataset.upsert_curve("C2", np.array([1.0, np.inf, 3.0]), unit="%")
    layout = TabletLayout(
        [TrackDefinition(
            "gas", "Gas", TrackKind.GAS,
            curve_mnemonics=["TG", "C1", "C2"],
        )],
        vertical_index_id="time" if use_time else None,
    )
    view = TabletView()
    try:
        view.set_layout_and_dataset(layout, dataset)
        click_axis = 61.0 if use_time else 101.1
        choices = view._curve_value_choices("gas", 0.5, click_axis)
        assert len(choices) == 1
        payload, caption = choices[0]
        assert payload["mnemonic"] == "TG"
        assert payload["value"] == 20.0
        assert payload["depth"] == depth[1]
        assert payload["axis_value"] == (60.0 if use_time else 101.0)
        assert payload["axis_id"] == ("time" if use_time else None)
        assert "TG" in caption
        assert view._curve_value_payload(
            "gas", 0.5, click_axis, mnemonic="C1",
        ) is None
        assert view._curve_value_payload(
            "gas", 0.5, click_axis, mnemonic="C2",
        ) is None
        assert view._curve_value_choices("gas", 0.5, float("nan")) == ()
        assert view._curve_value_choices("gas", 0.5, float("inf")) == ()
        np.testing.assert_array_equal(dataset.depth, depth)
        np.testing.assert_array_equal(
            dataset.curve_by_mnemonic("C1").values,
            np.array([2.0, np.nan, 4.0]),
        )
    finally:
        view.clear()
        view.close()
        view.deleteLater()
        qapp.processEvents()
