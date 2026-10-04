from __future__ import annotations

import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.printing.gas_ratio_reference import (
    reference_pairs,
    ratio_reference_tracks,
    ratio_reference_summary_uri,
)
from geoworkbench.services.localization import AppLanguage


def _dataset() -> Dataset:
    dataset = Dataset(
        "reference",
        "Reference",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0, 103.0]),
    )
    for name, values in {
        "WH": [10.0, np.nan, 30.0, 40.0],
        "BH": [2.0, 3.0, np.nan, 5.0],
        "CH": [0.1, 0.2, 0.3, 0.4],
        "C1_C2": [4.0, 5.0, 6.0, 7.0],
        "C1_C3": [8.0, 9.0, 10.0, 11.0],
        "C1_C4": [12.0, 13.0, 14.0, 15.0],
        "C1_C5": [16.0, 17.0, 18.0, 19.0],
    }.items():
        dataset.curves[name] = CurveData(
            CurveMetadata(name, name, name, "ratio", None, dataset.dataset_id), np.array(values)
        )
    return dataset


def test_reference_overlay_compares_wh_bh_on_identical_scale() -> None:
    tracks = ratio_reference_tracks(tuple(_dataset().curves.values()))
    by_name = {curve.metadata.original_mnemonic: (scale, group) for curve, scale, group in tracks}
    assert by_name["WH"] == by_name["BH"]
    assert by_name["CH"][1] != by_name["WH"][1]
    assert by_name["CH"][0].logarithmic is False
    assert set(by_name) == {"WH", "BH", "CH"}


def test_crossplot_keeps_paired_source_rows_and_methane_fraction() -> None:
    x, fraction, depth = reference_pairs(_dataset(), "BH")
    np.testing.assert_array_equal(x, [2.0, 5.0])
    np.testing.assert_allclose(fraction, [0.9, 0.6])
    np.testing.assert_array_equal(depth, [100.0, 103.0])


def test_reference_summary_handles_complete_pixler_profiles_without_mutating_source(qapp) -> None:
    dataset = _dataset()
    before = {name: curve.values.copy() for name, curve in dataset.curves.items()}
    for language in AppLanguage:
        assert ratio_reference_summary_uri(dataset, language).startswith("data:image/png;base64,")
    for name, curve in dataset.curves.items():
        np.testing.assert_array_equal(curve.values, before[name])
