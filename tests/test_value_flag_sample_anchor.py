from types import SimpleNamespace

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def test_value_flag_uses_actual_nearest_sample_axis_and_value(qapp, monkeypatch):
    dataset = Dataset("flags", "Flags", DatasetKind.GTI, DepthDomain.MD,
                      np.asarray([100.0, 101.0, 102.0]))
    dataset.upsert_curve("TG", np.asarray([10.0, 20.0, 30.0]), unit="%")
    original_depth = dataset.depth.copy()
    view = TabletView()
    view.set_layout_model(TabletLayout([TrackDefinition("gas", "Gas", TrackKind.GAS,
                                                       curve_mnemonics=["TG"])]))
    view.set_dataset(dataset)
    pointer = SimpleNamespace(local_y=100.4, local_x=0.5,
                              target=SimpleNamespace(object_id="TG"))
    monkeypatch.setattr(view, "hit_test_curve", lambda *args, **kwargs: pointer)
    try:
        payload = view._curve_value_payload("gas", 0.5, 100.4)
        assert payload is not None
        assert payload["axis_value"] == payload["depth"] == 100.0
        assert payload["value"] == 10.0
        assert payload["unit"] == "%"
        assert payload["axis_id"] == view.vertical_index_id
        np.testing.assert_array_equal(dataset.depth, original_depth)
        pointer.local_y = float("nan")
        assert view._curve_value_payload("gas", 0.5, float("nan")) is None
        pointer.local_y = 101.0
        dataset.curve_by_mnemonic("TG").values[1] = float("nan")
        assert view._curve_value_payload("gas", 0.5, 101.0) is None
    finally:
        view.clear()
        view.close()
