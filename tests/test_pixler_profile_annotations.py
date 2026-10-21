import pytest
from geoworkbench.printing.pixler_profile_annotations import (
    pixler_profile_trend, pixler_profile_caption,
)
from geoworkbench.services.fluid_phase_contract import FluidPhaseContract
from geoworkbench.services.localization import AppLanguage


@pytest.mark.parametrize("values,expected", [
    ([9, 20, 40, 80], "rising"), ([9, 8, 6, 4], "falling"),
    ([9, 8, 8, 8], "flat"), ([9, 8, 6, 10], "mixed"),
    ([9, 8, 0, 10], "unknown"), ([9, 8, float("nan"), 10], "unknown"),
])
def test_trend_describes_only_observed_profile_geometry(values, expected):
    assert pixler_profile_trend(values) == expected


@pytest.mark.parametrize("language", list(AppLanguage))
def test_rising_ratios_do_not_invent_phase_when_interval_evidence_is_missing(language):
    phase, trend = pixler_profile_caption(FluidPhaseContract.INDETERMINATE, "rising", language)
    assert phase and trend
    assert phase == pixler_profile_caption(FluidPhaseContract.INDETERMINATE, "falling", language)[0]
    assert phase != pixler_profile_caption(FluidPhaseContract.GAS, "rising", language)[0]


@pytest.mark.parametrize("language", list(AppLanguage))
def test_qualitative_tendencies_are_distinct_and_do_not_change_phase_caption(language):
    from geoworkbench.printing.pixler_profile_annotations import pixler_visual_tendency
    cues = [pixler_visual_tendency(trend, language) for trend in ("rising", "falling", "mixed")]
    assert len(set(cues)) == 3
    assert cues[0].startswith("↑")
    assert cues[1].startswith("↓")
    assert cues[2].startswith("↕")
    assert pixler_visual_tendency("invalid", language) == pixler_visual_tendency("unknown", language)
