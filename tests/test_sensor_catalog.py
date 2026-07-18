from __future__ import annotations

import json
from pathlib import Path

import pytest

from geoworkbench.catalogs.sensors import (
    SensorCatalog,
    default_sensor_catalog,
    normalize_sensor_key,
)


def test_default_sensor_catalog_contains_reference_and_legacy_fields() -> None:
    catalog = default_sensor_catalog()

    assert len(catalog.sensors) >= 400
    assert catalog.match("TGAS").definition.canonical_mnemonic == "TG"
    assert catalog.match("CH4").definition.canonical_mnemonic == "C1"
    assert catalog.match("С1").definition.canonical_mnemonic == "C1"
    assert catalog.match("BIT_RPM").definition.canonical_mnemonic == "RPM"
    assert catalog.match("", description="Содержание метана").definition.canonical_mnemonic == "C1"


def test_sensor_catalog_uses_units_to_choose_ambiguous_alias() -> None:
    catalog = default_sensor_catalog()
    match = catalog.match("Глубина забоя", unit="м")

    assert match is not None
    assert match.definition.family == "drilling_depth"
    assert match.definition.unit == "м"


def test_sensor_catalog_can_load_external_json(tmp_path: Path) -> None:
    payload = {
        "schema_version": 1,
        "catalog_name": "Custom Sensors",
        "sources": ["unit-test"],
        "sensors": [
            {
                "id": "custom_pressure",
                "canonical_mnemonic": "P_CUSTOM",
                "aliases": ["PCUST"],
                "name_ru": "Пользовательское давление",
                "short_name_ru": "Давление",
                "unit": "MPa",
                "family": "pressure",
                "category": "drilling",
                "default_min": 0,
                "default_max": 50,
                "color": "#123456",
                "source": "unit-test",
            }
        ],
        "legacy_fields": [],
    }
    path = tmp_path / "sensors.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    catalog = SensorCatalog.from_json(path)

    assert catalog.catalog_name == "Custom Sensors"
    assert catalog.match("PCUST").definition.sensor_id == "custom_pressure"
    assert catalog.search("давление") == catalog.sensors


def test_sensor_catalog_rejects_unknown_family() -> None:
    payload = {
        "schema_version": 1,
        "catalog_name": "Broken",
        "sensors": [
            {
                "id": "broken",
                "canonical_mnemonic": "BROKEN",
                "aliases": [],
                "name_ru": "Broken",
                "family": "unknown-family",
                "category": "other",
                "color": "#000000",
            }
        ],
    }

    with pytest.raises(ValueError, match="семейство"):
        SensorCatalog.from_json(payload)


def test_sensor_key_normalization_handles_legacy_cyrillic_homoglyphs() -> None:
    assert normalize_sensor_key(" С1 ") == "C1"
    assert normalize_sensor_key("TG_CALC") == "TGCALC"
