from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.services.daily_las_growth import (
    DailyLasGrowthError, analyze_daily_las_growth, apply_daily_las_growth,
)
from test_daily_las_growth import _dataset, _add_curve


def _pair():
    target = _dataset("old", [100.0, 101.0], [10.0, 11.0])
    source = _dataset("new", [101.0, 102.0], [11.0, 12.0])
    target_curve = next(iter(target.curves.values()))
    target_curve.metadata = replace(target_curve.metadata, original_mnemonic="S106")
    return target, source


def _analyze(target, source):
    return analyze_daily_las_growth(target, source, source_name="daily.las", source_sha256="a" * 64)


def test_append_maps_known_alias_and_preserves_existing_native_name():
    target, source = _pair()
    plan = _analyze(target, source)
    assert plan.matched_curve_mnemonics == (("ROP", "S106"),)
    apply_daily_las_growth(target, source, plan)
    curve = next(iter(target.curves.values()))
    assert curve.metadata.original_mnemonic == "S106"
    np.testing.assert_array_equal(curve.values, [10.0, 11.0, 12.0])
    assert len(target.curves) == 1


def test_canonical_alias_does_not_bypass_unit_validation():
    target, source = _pair()
    curve = next(iter(source.curves.values()))
    curve.metadata = replace(curve.metadata, unit="ft/h")
    with pytest.raises(DailyLasGrowthError, match="Единица"):
        _analyze(target, source)
    assert len(target.depth) == 2


def test_ambiguous_native_parameters_are_rejected():
    target, source = _pair()
    other = _add_curve(target, "SECOND_ROP", [10, 11], unit="m/h")
    other.metadata = replace(other.metadata, canonical_mnemonic="ROP")
    with pytest.raises(DailyLasGrowthError, match="Неоднозначное"):
        _analyze(target, source)


def test_two_source_aliases_cannot_overwrite_one_native_channel():
    target, source = _pair()
    other = _add_curve(source, "SECOND_ROP", [11, 12], unit="m/h")
    other.metadata = replace(other.metadata, canonical_mnemonic="ROP")
    with pytest.raises(DailyLasGrowthError, match="Несколько каналов"):
        _analyze(target, source)


def test_exact_name_wins_even_when_other_channels_share_its_canonical_parameter():
    target, source = _pair()
    next(iter(source.curves.values())).metadata = replace(
        next(iter(source.curves.values())).metadata, original_mnemonic="S106",
    )
    other = _add_curve(target, "OTHER_ROP", [20, 21], unit="m/h")
    other.metadata = replace(other.metadata, canonical_mnemonic="ROP")
    plan = _analyze(target, source)
    assert plan.missing_curve_mnemonics == ("OTHER_ROP",)
    apply_daily_las_growth(target, source, plan)
    assert np.isnan(other.values[-1])


def test_relative_gas_is_not_mapped_to_absolute_component():
    target, source = _pair()
    next(iter(target.curves.values())).metadata = replace(
        next(iter(target.curves.values())).metadata, canonical_mnemonic="C1", unit="%",
    )
    next(iter(source.curves.values())).metadata = replace(
        next(iter(source.curves.values())).metadata, canonical_mnemonic="C1_REL", unit="%",
    )
    with pytest.raises(DailyLasGrowthError, match="Схема LAS"):
        _analyze(target, source)
