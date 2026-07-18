from __future__ import annotations

import json

from geoworkbench.catalogs.sensors import default_sensor_catalog
from geoworkbench.services.mnemonic_registry import UserMnemonicRegistry, UserMnemonicRule


class MemorySettings:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def value(self, key: str, default: str = "") -> str:
        return self.data.get(key, default)

    def setValue(self, key: str, value: str) -> None:
        self.data[key] = value

    def sync(self) -> None:
        pass


def test_user_rule_has_priority_over_base_catalog() -> None:
    settings = MemorySettings()
    registry = UserMnemonicRegistry(settings)
    registry.upsert(
        UserMnemonicRule("r1", "tgas", "TOTAL_GAS_CUSTOM", "Газ общий", "%", "gas", "gas")
    )
    match = registry.catalog(default_sensor_catalog()).match("TGAS", unit="%")
    assert match is not None
    assert match.definition.canonical_mnemonic == "TOTAL_GAS_CUSTOM"
    assert match.definition.source == "Пользовательский словарь"


def test_registry_persists_and_exports(tmp_path) -> None:
    settings = MemorySettings()
    registry = UserMnemonicRegistry(settings)
    registry.upsert(
        UserMnemonicRule("r1", "vendor_ch4", "C1", "Метан", "%", "gas", "gas", ("CH4_VENDOR",))
    )
    assert registry.rules()[0].foreign_mnemonic == "vendor_ch4"
    path = tmp_path / "mnemonics.json"
    registry.export_json(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    other = UserMnemonicRegistry(MemorySettings())
    other.import_json(path)
    assert other.catalog().match("CH4_VENDOR").definition.canonical_mnemonic == "C1"
