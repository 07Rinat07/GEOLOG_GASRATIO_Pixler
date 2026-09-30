from __future__ import annotations

import json
from pathlib import Path

import pytest

from geoworkbench.acquisition.wits0_live_forms import (
    CUSTOM_LIVE_FORM_ID,
    WITS0_LIVE_FORM_STATE_SCHEMA_VERSION,
    Wits0LiveFormSettings,
    Wits0SavedAlarmRule,
    Wits0SavedLiveFormState,
    live_channel_key,
    live_form_definitions,
    live_panel_definitions,
    live_panel_key,
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


def test_operator_dashboard_separates_incompatible_engineering_scales() -> None:
    panels = {item.panel_id: item for item in live_panel_definitions()}

    assert live_panel_key("DEPTMEAS") == "depth"
    assert live_panel_key("ROPA") == "rate"
    assert live_panel_key("HKLA") == "load"
    assert live_panel_key("RPMA") == "rotation"
    assert live_panel_key("TORQA") == "torque"
    assert live_panel_key("SPPA") == "pressure"
    assert live_panel_key("SPM1") == "pumps"
    assert live_panel_key("MFIA") == "flow"
    assert live_panel_key("MDIA") == "mud_density"
    assert live_panel_key("MTIA") == "mud_temperature"
    assert live_panel_key("TVOLACT") == "pits"
    assert live_panel_key("GASA") == "gas_total"
    assert live_panel_key("METHA") == "gas_components"

    assert "rpm" not in panels["load"].channel_keys
    assert "torque" not in panels["rotation"].channel_keys
    assert "total_gas" not in panels["gas_components"].channel_keys
    assert len({key for panel in panels.values() for key in panel.channel_keys}) == sum(
        len(panel.channel_keys) for panel in panels.values()
    )


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


def test_wits_live_view_exposes_editable_persistent_form_selector() -> None:
    source = (ROOT / "src/geoworkbench/ui/wits0_live_view.py").read_text(
        encoding="utf-8"
    )
    assert "self.form_combo = QComboBox(" in source
    assert 'toolbar.setObjectName("wits0LiveToolbar")' in source
    assert "live_form_definitions()" in source
    assert "select_live_curve_ids" in source
    assert "Wits0LiveFormSettings" in source
    assert "def _save_current_form(" in source
    assert "def _reset_current_form(" in source
    assert "panel_order, hidden_panel_ids = self.dashboard.panel_layout()" in source
    assert "self.dashboard.set_panel_layout(" in source
    selection_body = source[
        source.index("def _curve_selection_changed")
        : source.index("def _dashboard_range_changed")
    ]
    assert "CUSTOM_LIVE_FORM_ID" not in selection_body



class _MemorySettings:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def value(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def setValue(self, key: str, value: object) -> None:
        self.values[key] = value

    def remove(self, key: str) -> None:
        self.values.pop(key, None)

    def sync(self) -> None:
        return None


def test_live_form_settings_roundtrip_operator_overrides_by_mnemonic() -> None:
    storage = _MemorySettings()
    settings = Wits0LiveFormSettings(storage)
    state = Wits0SavedLiveFormState(
        form_id="drilling",
        selected_mnemonics=("HOLE_DEPTH", "ROP", "WOB"),
        axis_mode="depth",
        auto_follow=False,
        follow_span=250.0,
        max_points=4_000,
        sidebar_visible=False,
        panel_order=("gas_total", "gas_components", "depth"),
        hidden_panel_ids=("depth",),
        panel_x_ranges=(
            ("gas_components|ppm", 0.0, 500.0),
            ("gas_components|%", 0.0, 5.0),
        ),
        alarm_rules=(
            Wits0SavedAlarmRule(
                mnemonic="SPP",
                minimum=50.0,
                maximum=350.0,
                hysteresis=5.0,
                debounce_samples=3,
            ),
            Wits0SavedAlarmRule(
                mnemonic="H2S",
                maximum=10.0,
                hysteresis=1.0,
                debounce_samples=2,
            ),
        ),
    )

    settings.save(state)

    assert settings.load("drilling") == state
    settings.reset("drilling")
    assert settings.load("drilling") is None


def test_live_form_settings_migrate_schema_v1_without_panel_overrides() -> None:
    storage = _MemorySettings()
    settings = Wits0LiveFormSettings(storage)
    storage.setValue(
        "wits0/live-forms/drilling",
        json.dumps(
            {
                "form_id": "drilling",
                "selected_mnemonics": ["ROP", "WOB"],
                "axis_mode": "depth",
                "auto_follow": False,
                "follow_span": 180.0,
                "max_points": 2500,
                "sidebar_visible": False,
                "schema_version": 1,
            }
        ),
    )

    migrated = settings.load("drilling")

    assert migrated is not None
    assert migrated.schema_version == WITS0_LIVE_FORM_STATE_SCHEMA_VERSION
    assert migrated.selected_mnemonics == ("ROP", "WOB")
    assert migrated.panel_order == ()
    assert migrated.hidden_panel_ids == ()
    assert migrated.panel_x_ranges == ()
    assert migrated.alarm_rules == ()


def test_live_form_settings_migrate_schema_v2_without_x_ranges() -> None:
    storage = _MemorySettings()
    settings = Wits0LiveFormSettings(storage)
    storage.setValue(
        "wits0/live-forms/gas",
        json.dumps(
            {
                "form_id": "gas",
                "selected_mnemonics": ["C1", "CO2"],
                "axis_mode": "time",
                "auto_follow": True,
                "follow_span": 600.0,
                "max_points": 2000,
                "sidebar_visible": True,
                "panel_order": ["gas_total", "gas_components"],
                "hidden_panel_ids": ["gas_total"],
                "schema_version": 2,
            }
        ),
    )

    migrated = settings.load("gas")

    assert migrated is not None
    assert migrated.schema_version == WITS0_LIVE_FORM_STATE_SCHEMA_VERSION
    assert migrated.panel_order == ("gas_total", "gas_components")
    assert migrated.hidden_panel_ids == ("gas_total",)
    assert migrated.panel_x_ranges == ()
    assert migrated.alarm_rules == ()


def test_live_form_settings_migrate_schema_v3_without_alarm_rules() -> None:
    storage = _MemorySettings()
    settings = Wits0LiveFormSettings(storage)
    storage.setValue(
        "wits0/live-forms/gas",
        json.dumps(
            {
                "form_id": "gas",
                "selected_mnemonics": ["TG", "C1"],
                "axis_mode": "time",
                "auto_follow": True,
                "follow_span": 600.0,
                "max_points": 2000,
                "sidebar_visible": True,
                "panel_order": ["gas_total", "gas_components"],
                "hidden_panel_ids": [],
                "panel_x_ranges": [["gas_components|ppm", 0.0, 500.0]],
                "schema_version": 3,
            }
        ),
    )

    migrated = settings.load("gas")

    assert migrated is not None
    assert migrated.schema_version == WITS0_LIVE_FORM_STATE_SCHEMA_VERSION
    assert migrated.panel_x_ranges == (("gas_components|ppm", 0.0, 500.0),)
    assert migrated.alarm_rules == ()


def test_live_form_state_rejects_invalid_and_duplicate_alarm_rules() -> None:
    with pytest.raises(ValueError, match="at least one alarm limit"):
        Wits0SavedAlarmRule(mnemonic="SPP")

    with pytest.raises(ValueError, match="duplicates"):
        Wits0SavedLiveFormState(
            form_id="drilling",
            alarm_rules=(
                Wits0SavedAlarmRule(mnemonic="SPP", maximum=300.0),
                Wits0SavedAlarmRule(mnemonic="spp", maximum=350.0),
            ),
        )


def test_live_form_settings_fail_closed_on_malformed_alarm_rule() -> None:
    storage = _MemorySettings()
    settings = Wits0LiveFormSettings(storage)
    storage.setValue(
        "wits0/live-forms/drilling",
        json.dumps(
            {
                "form_id": "drilling",
                "selected_mnemonics": ["SPP"],
                "alarm_rules": [
                    {
                        "mnemonic": "SPP",
                        "minimum": 400.0,
                        "maximum": 300.0,
                        "hysteresis": 1.0,
                        "debounce_samples": 2,
                    }
                ],
                "schema_version": WITS0_LIVE_FORM_STATE_SCHEMA_VERSION,
            }
        ),
    )

    assert settings.load("drilling") is None


def test_live_form_state_rejects_invalid_panel_x_range() -> None:
    with pytest.raises(ValueError, match="finite min < max"):
        Wits0SavedLiveFormState(
            form_id="gas",
            panel_x_ranges=(("gas_components|ppm", 10.0, 10.0),),
        )


def test_all_operator_forms_have_context_descriptions() -> None:
    for definition in live_form_definitions():
        assert definition.description("ru")
        assert definition.description("kk")
        assert definition.description("en")
