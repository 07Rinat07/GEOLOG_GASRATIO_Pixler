"""WOB curve clicks show source force in metric tonnes-force."""
from types import SimpleNamespace

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


def test_wob_curve_click_displays_tonnes_force_without_changing_source(qapp, monkeypatch):
    dataset = Dataset(
        "wob-plot", "WOB", DatasetKind.GTI, DepthDomain.MD,
        np.array([1000., 1001., 1002.]),
    )
    dataset.upsert_curve("WOB", np.array([98.0665, 196.133, 294.1995]), unit="kN")
    original = dataset.curve_by_mnemonic("WOB").values.copy()
    view = TabletView()
    view.set_layout_model(TabletLayout([
        TrackDefinition("wob", "WOB", TrackKind.CURVE, curve_mnemonics=["WOB"]),
    ]))
    view.set_dataset(dataset)
    pointer = SimpleNamespace(
        local_y=1001., local_x=0.5, target=SimpleNamespace(object_id="WOB"),
    )
    monkeypatch.setattr(view, "hit_test_curve", lambda *args, **kwargs: pointer)
    try:
        payload = view._curve_value_payload("wob", 0.5, 1001.)
        assert payload is not None
        assert payload["value"] == 196.133
        assert payload["unit"] == "kN"
        assert payload["display_value"] == "20 тс"
        assert payload["depth"] == 1001.
        assert "20 тс" in view._curve_value_caption(payload)
        np.testing.assert_array_equal(dataset.curve_by_mnemonic("WOB").values, original)
    finally:
        view.clear()
        view.close()
