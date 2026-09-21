from __future__ import annotations

from pathlib import Path

from geoworkbench.acquisition.wits0_live_forms import (
    CUSTOM_LIVE_FORM_ID,
    live_channel_key,
    live_form_definitions,
    select_live_curve_ids,
)
from geoworkbench.catalogs.sensors import default_sensor_catalog
from geoworkbench.forms.templates import factory_templates


ROOT = Path(__file__).resolve().parents[1]


def test_universal_live_form_resolves_standard_wits_and_legacy_semantics() -> None:
    assert live_channel_key("DEPTMEAS") == "hole_depth"
    assert live_channel_key("DEPTBITM") == "bit_depth"
    assert live_channel_key("BPOS") == "block_position"
    assert live_channel_key("HKLA") == "hook_load"
    assert live_channel_key("WOBA") == "wob"
    assert live_channel_key("TORQA") == "torque"
    assert live_channel_key("SPPA") == "spp"
    assert live_channel_key("TVOL01") == "pit_1"
    assert live_channel_key("METHANE") == "c1"
    assert live_channel_key("IPENTANE") == "ic5"

    curves = (
        ("depth", "HOLE_DEPTH", "DEPTMEAS"),
        ("wob", "WOB", "WOBA"),
        ("pressure", "SPP", "SPPA"),
        ("pit1", "SENSOR_711", "TVOL01"),
        ("methane", "C1", "METHANE"),
        ("unknown", "VENDOR_X", "VENDOR_X"),
    )
    selected = select_live_curve_ids("universal", curves)
    assert selected == ("depth", "wob", "pressure", "pit1", "methane")
    assert select_live_curve_ids("gas", curves) == ("methane",)
    assert select_live_curve_ids(CUSTOM_LIVE_FORM_ID, curves) == ()


def test_live_form_catalog_has_operator_presets() -> None:
    definitions = live_form_definitions()
    assert [item.form_id for item in definitions] == [
        "universal",
        "drilling",
        "hydraulics",
        "pits",
        "gas",
        "custom",
    ]
    universal = definitions[0]
    assert len(universal.channel_keys) >= 40
    assert "hole_depth" in universal.channel_keys
    assert "pit_8" in universal.channel_keys
    assert "nc5" in universal.channel_keys


def test_sensor_catalog_maps_standard_wits_names_to_geosight_semantics() -> None:
    catalog = default_sensor_catalog()
    expected = {
        "DEPTMEAS": "HOLE_DEPTH",
        "DEPTBITM": "BIT_DEPTH",
        "BLKPOS": "BLOCK_POSITION",
        "ROPA": "ROP",
        "HKLA": "HKLD",
        "STRGWT": "STRING_WEIGHT",
        "WOBA": "WOB",
        "TORQA": "TQ",
        "RPMA": "RPM",
        "SPPA": "SPP",
        "SPM1": "SENSOR_50",
        "MFIA": "FLOW_IN",
        "MFOA": "FLOW_OUT",
        "MDIA": "MW_IN",
        "MDOA": "MW_OUT",
        "MTIA": "TEMP_IN",
        "MTOA": "TEMP_OUT",
        "TVOLACT": "PIT_VOL",
        "TVOL01": "SENSOR_711",
        "TVOL08": "SENSOR_724",
        "METHA": "C1",
        "ETHA": "C2",
        "PROPA": "C3",
        "IBUTA": "IC4",
        "NBUTA": "NC4",
        "IPENTA": "IC5",
        "NPENTA": "NC5",
    }
    for mnemonic, canonical in expected.items():
        match = catalog.match(mnemonic)
        assert match is not None, mnemonic
        assert match.definition.canonical_mnemonic == canonical


def test_engineering_control_template_is_full_universal_wits_form() -> None:
    form = factory_templates("ru")["factory-engineering-control-time"]
    bindings = {
        binding.canonical_parameter_id
        for column in form.columns
        for track in column.tracks
        for binding in track.bindings
    }
    required = {
        "HOLE_DEPTH",
        "BIT_DEPTH",
        "BIT_DISTANCE_TO_BOTTOM",
        "BLOCK_POSITION",
        "BLOCK_SPEED",
        "ROP",
        "LAG_TIME",
        "HKLD",
        "STRING_WEIGHT",
        "WOB",
        "RPM",
        "TQ",
        "SPP",
        "SENSOR_50",
        "SENSOR_51",
        "SENSOR_52",
        "FLOW_IN",
        "FLOW_OUT",
        "MW_IN",
        "MW_OUT",
        "TEMP_IN",
        "TEMP_OUT",
        "PIT_VOL",
        "SENSOR_711",
        "SENSOR_724",
        "TOTAL_GAS",
        "C1",
        "C2",
        "C3",
        "IC4",
        "NC4",
        "IC5",
        "NC5",
        "CO2",
        "MS_H2S",
    }
    assert required <= bindings
    assert len(form.columns) >= 8


def test_wits_live_view_exposes_form_selector() -> None:
    source = (ROOT / "src/geoworkbench/ui/wits0_live_view.py").read_text(
        encoding="utf-8"
    )
    assert "self.form_combo = QComboBox(self)" in source
    assert "live_form_definitions()" in source
    assert "select_live_curve_ids" in source
    assert "CUSTOM_LIVE_FORM_ID" in source
