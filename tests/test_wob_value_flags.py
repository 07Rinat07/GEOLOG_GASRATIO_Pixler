"""Regression tests for factual WOB source value flags."""
import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.services.wob_value_flags import wob_channels, wob_value_at_depth


def _dataset(unit="kN"):
    dataset = Dataset(
        "wob", "WOB source", DatasetKind.GTI, DepthDomain.MD,
        np.array([1000., 1001., 1002., 1100.]),
    )
    dataset.upsert_curve("WOB", np.array([98.0665, np.nan, 196.133, 294.1995]), unit=unit)
    dataset.upsert_curve("HOOKLOAD", np.array([100., 101., 102., 103.]), unit="kN")
    dataset.upsert_curve("TG", np.array([1., 2., 3., 4.]), unit="%")
    return dataset


def test_wob_selects_actual_source_and_converts_force_without_mutation():
    dataset = _dataset()
    before = dataset.curve_by_mnemonic("WOB").values.copy()
    assert wob_channels(dataset) == ("WOB",)
    sample = wob_value_at_depth(dataset, "WOB", 1000.)
    assert sample is not None
    assert sample.source_value == pytest.approx(98.0665)
    assert sample.tonnes_force == pytest.approx(10.)
    assert sample.row_index == 0
    assert "MD 1000" in sample.caption
    np.testing.assert_array_equal(dataset.curve_by_mnemonic("WOB").values, before)


def test_wob_rejects_missing_gap_and_other_sensors():
    dataset = _dataset()
    assert wob_value_at_depth(dataset, "WOB", 1001.) is None
    assert wob_value_at_depth(dataset, "WOB", 1050.) is None
    assert wob_value_at_depth(dataset, "HOOKLOAD", 1000.) is None
    assert wob_value_at_depth(dataset, "TG", 1000.) is None
    assert wob_value_at_depth(dataset, "WOB", float("nan")) is None


@pytest.mark.parametrize("unit,value,expected", [
    ("тс", 12., 12.),
    ("kN", 98.0665, 10.),
    ("N", 9806.65, 1.),
    ("lbf", 2204.6226218488, 1.),
    ("klbf", 2.2046226218488, 1.),
])
def test_wob_supported_force_units(unit, value, expected):
    dataset = _dataset(unit)
    dataset.curve_by_mnemonic("WOB").values[0] = value
    sample = wob_value_at_depth(dataset, "WOB", 1000.)
    assert sample is not None
    assert sample.tonnes_force == pytest.approx(expected)


@pytest.mark.parametrize("unit", ["kg", "t", "ton", "", "%"])
def test_wob_rejects_ambiguous_or_mass_units(unit):
    dataset = _dataset(unit)
    assert wob_channels(dataset) == ()
    assert wob_value_at_depth(dataset, "WOB", 1000.) is None


def test_wob_duplicate_md_must_be_unambiguous():
    dataset = Dataset(
        "dup", "Duplicate MD", DatasetKind.GTI, DepthDomain.MD,
        np.array([1000., 1001., 1001., 1002.]),
    )
    dataset.upsert_curve("WOB", np.array([10., 12., 20., 13.]), unit="тс")
    assert wob_value_at_depth(dataset, "WOB", 1001.) is None
    dataset.curve_by_mnemonic("WOB").values[2] = 12.
    assert wob_value_at_depth(dataset, "WOB", 1001.).tonnes_force == pytest.approx(12.)


def test_wob_tvd_axis_is_not_md():
    dataset = Dataset(
        "tvd", "TVD", DatasetKind.GTI, DepthDomain.TVD,
        np.array([1000., 1001.]),
    )
    dataset.upsert_curve("WOB", np.array([10., 11.]), unit="тс")
    assert wob_value_at_depth(dataset, "WOB", 1001.) is None
