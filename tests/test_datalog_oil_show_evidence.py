"""Evidence-level audit of the uploaded DataLog / MOL oil-show worksheets."""

from dataclasses import FrozenInstanceError

import pytest

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.datalog_oil_show_evidence import (
    DATALOG_METHODS,
    LegacyShowGroup,
    ShowMethod,
    ShowQualityControls,
    audit_legacy_datalog_show,
)


def _sample(**kwargs: object) -> CuttingsSample:
    sample = CuttingsSample("sample-datalog-01", 1000.0, 1010.0)
    for key, value in kwargs.items():
        setattr(sample, key, value)
    return sample


def test_method_inventory_keeps_uv_plus_and_daylight_separate() -> None:
    assert {entry.method for entry in DATALOG_METHODS} == set(ShowMethod)
    assert len({entry.method for entry in DATALOG_METHODS}) == len(DATALOG_METHODS)
    modes = {entry.method: entry.observation_light for entry in DATALOG_METHODS}
    assert modes[ShowMethod.STAIN_DAYLIGHT] == "uv_minus"
    assert modes[ShowMethod.NATURAL_FLUORESCENCE_UV] == "uv_plus"
    assert modes[ShowMethod.SOLVENT_CUT_DAYLIGHT] == "uv_minus"
    assert modes[ShowMethod.SOLVENT_CUT_UV] == "uv_plus"
    assert modes[ShowMethod.RESIDUE_DAYLIGHT] == "uv_minus"
    assert modes[ShowMethod.RESIDUE_UV] == "uv_plus"
    assert modes[ShowMethod.CAPILLARY_EXTRACT_DAYLIGHT] == "uv_minus"
    assert modes[ShowMethod.CAPILLARY_EXTRACT_UV] == "uv_plus"


def test_empty_legacy_sample_is_unknown_not_negative_show() -> None:
    sample = _sample()
    before = repr(sample)
    result = audit_legacy_datalog_show(sample)
    assert result.recorded == ()
    assert result.quality_warnings == ()
    assert not result.candidate_for_human_review
    assert "stain_unrecorded" in result.missing_method_details
    assert "florovskaya_unrecorded" in result.missing_method_details
    assert not result.proves_fluid_phase
    assert not result.proves_hydrocarbon_saturation
    assert repr(sample) == before


def test_legacy_fields_are_not_transferred_to_unverified_uv_conditions() -> None:
    sample = _sample(
        lba_group=1, lba_type_id="ЛБ", lba_intensity=2, lba_color="БГ",
        lba_distribution="Spotty", lba_cut="Streaming",
        lba_cut_speed="Slow", lba_cut_color="Straw",
        lba_residue_type="Trace", lba_residue_color="Amber",
        lba_stain="Pinpoint", lba_odour="Faint",
    )
    before = repr(sample)
    result = audit_legacy_datalog_show(sample)
    groups = {record.group: dict(record.attributes) for record in result.recorded}
    assert groups[LegacyShowGroup.FLOROVSKAYA_CAPILLARY] == {
        "lba_group": 1, "lba_type_id": "ЛБ",
        "lba_intensity": 2, "lba_color": "БГ",
    }
    assert groups[LegacyShowGroup.SOLVENT_CUT_UNSPLIT] == {
        "lba_cut": "Streaming", "lba_cut_speed": "Slow",
        "lba_cut_color": "Straw",
    }
    assert groups[LegacyShowGroup.RESIDUE_UNSPLIT] == {
        "lba_residue_type": "Trace", "lba_residue_color": "Amber",
    }
    assert groups[LegacyShowGroup.NATURAL_FLUORESCENCE_UNSPLIT] == {
        "lba_distribution": "Spotty",
    }
    assert not result.has_all_separately_recorded_datalog_methods
    assert "natural_fluorescence_area_percent_and_brightness_not_separated" in result.missing_method_details
    assert "solvent_cut_uv_minus_and_uv_plus_not_separated" in result.missing_method_details
    assert "residue_uv_minus_and_uv_plus_not_separated" in result.missing_method_details
    assert "solvent_blank_unverified" in result.quality_warnings
    assert result.candidate_for_human_review
    assert repr(sample) == before


def test_background_controls_only_affect_qc_not_raw_attributes() -> None:
    sample = _sample(lba_cut="Blooming", lba_stain="Spotty")
    controls = ShowQualityControls(
        depth_lag_verified=True,
        mud_background_checked=True,
        spot_plate_clean_checked=True,
        solvent_blank_checked=True,
        potential_mud_additive_contamination=False,
        coal_or_organic_interference=False,
        mineral_fluorescence_interference=False,
    )
    result = audit_legacy_datalog_show(sample, quality=controls)
    assert result.quality_warnings == ()
    assert result.candidate_for_human_review
    assert len(result.recorded) == 2


@pytest.mark.parametrize(
    "key",
    (
        "potential_mud_additive_contamination",
        "coal_or_organic_interference",
        "mineral_fluorescence_interference",
    ),
)
def test_known_interference_forces_caution_without_deleting_observation(key: str) -> None:
    sample = _sample(lba_cut="Flash", lba_color="БГ")
    controls = ShowQualityControls(**{key: True})
    result = audit_legacy_datalog_show(sample, quality=controls)
    assert key in result.quality_warnings
    assert not result.candidate_for_human_review
    assert len(result.recorded) == 2
    assert not result.proves_fluid_phase


def test_none_label_is_a_recorded_result_not_missing_data() -> None:
    result = audit_legacy_datalog_show(_sample(lba_odour="None"))
    assert len(result.recorded) == 1
    assert result.recorded[0].group is LegacyShowGroup.ODOUR
    assert result.recorded[0].attributes == (("lba_odour", "None"),)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("lba_group", -1), ("lba_group", 6),
        ("lba_intensity", 0), ("lba_intensity", 7),
        ("lba_intensity", True), ("lba_color", 8),
        ("lba_cut_speed", False),
    ),
)
def test_invalid_stored_values_are_reported_not_coerced(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        audit_legacy_datalog_show(_sample(**{field: value}))


def test_invalid_depth_and_qc_types_are_rejected() -> None:
    with pytest.raises(ValueError, match="MD"):
        audit_legacy_datalog_show(_sample(top_depth=float("nan")))
    with pytest.raises(ValueError, match="sample depths"):
        audit_legacy_datalog_show(_sample(bottom_depth=999.0))
    with pytest.raises(ValueError, match="depth_lag_verified"):
        audit_legacy_datalog_show(
            _sample(lba_odour="Faint"),
            quality=ShowQualityControls(depth_lag_verified="yes"),  # type: ignore[arg-type]
        )


def test_result_is_frozen_and_does_not_classify_oil_gas_or_water() -> None:
    result = audit_legacy_datalog_show(
        _sample(lba_group=3, lba_color="ОЖ", lba_intensity=5),
    )
    assert result.candidate_for_human_review
    assert not result.proves_hydrocarbon_saturation
    assert not result.proves_fluid_phase
    with pytest.raises(FrozenInstanceError):
        result.candidate_for_human_review = False  # type: ignore[misc]
