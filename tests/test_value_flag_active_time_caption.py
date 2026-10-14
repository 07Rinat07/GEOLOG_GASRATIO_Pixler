"""VALUE pickers disclose actual time coordinates without substituting MD."""

import numpy as np
import pytest

from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("time_kind", ["relative", "datetime"])
def test_value_picker_displays_actual_time_and_depth_for_repeated_md(
    qapp, language, time_kind,
):
    depth = np.array([100.0, 100.0, 101.0])
    gas = np.array([10.0, 20.0, 30.0])
    dataset = Dataset("timed-value", "Timed value", DatasetKind.GTI, DepthDomain.MD, depth)
    if time_kind == "relative":
        time_values = np.array([0.0, 60.0, 120.0])
        time_type = IndexType.RELATIVE_TIME
        unit = "s"
        expected = "TIME: 60 s"
    else:
        time_values = np.array(
            ["2026-10-14T08:00:00", "2026-10-14T08:01:00", "2026-10-14T08:02:00"],
            dtype="datetime64[s]",
        )
        time_type = IndexType.DATETIME
        unit = None
        expected = "TIME: 2026-10-14T08:01:00"
    dataset.add_index(DatasetIndex(
        "time", "TIME", time_type, IndexRole.TIME, unit, time_values,
    ))
    dataset.upsert_curve("TG", gas, unit="%")
    layout = TabletLayout(
        [TrackDefinition("gas", "Gas", TrackKind.GAS, curve_mnemonics=["TG"])],
        vertical_index_id="time",
    )
    view = TabletView(language=language)
    try:
        view.set_layout_and_dataset(layout, dataset)
        sample_axis = float(view._axis_values()[1])
        payload = view._curve_value_payload("gas", 0.5, sample_axis, mnemonic="TG")
        assert payload is not None
        assert payload["axis_id"] == "time"
        assert payload["axis_value"] == sample_axis
        assert payload["depth"] == 100.0
        assert payload["value"] == 20.0
        assert payload["axis_caption"] == expected
        caption = view._curve_value_caption(payload)
        assert expected in caption
        assert caption.startswith("TG: 20 % · ")
        assert caption.endswith(" · 100 м") or caption.endswith(" · 100 m")
        np.testing.assert_array_equal(dataset.depth, depth)
        np.testing.assert_array_equal(dataset.curve_by_mnemonic("TG").values, gas)
        np.testing.assert_array_equal(dataset.indexes["time"].values, time_values)
    finally:
        view.clear()
        view.close()
        view.deleteLater()
        qapp.processEvents()


def test_depth_value_picker_keeps_existing_single_depth_caption(qapp):
    dataset = Dataset(
        "depth-value", "Depth value", DatasetKind.GTI,
        DepthDomain.MD, np.array([100.0, 101.0]),
    )
    dataset.upsert_curve("TG", np.array([10.0, 20.0]), unit="%")
    view = TabletView()
    try:
        view.set_layout_and_dataset(
            TabletLayout([TrackDefinition(
                "gas", "Gas", TrackKind.GAS, curve_mnemonics=["TG"],
            )]),
            dataset,
        )
        payload = view._curve_value_payload("gas", 0.5, 101.0, mnemonic="TG")
        assert payload is not None
        assert "axis_caption" not in payload
        assert view._curve_value_caption(payload).startswith("TG: 20 % · 101 ")
    finally:
        view.clear()
        view.close()
        view.deleteLater()
        qapp.processEvents()
