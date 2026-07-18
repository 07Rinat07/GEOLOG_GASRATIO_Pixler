from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from PySide6.QtCore import QSettings

from geoworkbench.catalogs.sensors import SensorCatalog, SensorDefinition, default_sensor_catalog


@dataclass(frozen=True, slots=True)
class UserMnemonicRule:
    rule_id: str
    foreign_mnemonic: str
    canonical_mnemonic: str
    name_ru: str
    unit: str = ""
    category: str = "other"
    family: str = "other"
    aliases: tuple[str, ...] = ()
    default_min: float | None = None
    default_max: float | None = None
    color: str = "#2563eb"

    def validate(self) -> UserMnemonicRule:
        foreign = self.foreign_mnemonic.strip()
        canonical = self.canonical_mnemonic.strip().upper()
        name = self.name_ru.strip()
        if not foreign:
            raise ValueError("Чужая мнемоника обязательна")
        if not canonical:
            raise ValueError("Каноническая мнемоника обязательна")
        if not name:
            raise ValueError("Название параметра обязательно")
        aliases = tuple(dict.fromkeys(x.strip() for x in self.aliases if x.strip()))
        return UserMnemonicRule(
            self.rule_id.strip() or str(uuid4()),
            foreign,
            canonical,
            name,
            self.unit.strip(),
            self.category.strip() or "other",
            self.family.strip() or "other",
            aliases,
            self.default_min,
            self.default_max,
            self.color.strip().lower() or "#2563eb",
        )

    def to_sensor(self) -> SensorDefinition:
        value = self.validate()
        aliases = tuple(dict.fromkeys((value.foreign_mnemonic, *value.aliases)))
        return SensorDefinition(
            sensor_id=f"user:{value.rule_id}",
            canonical_mnemonic=value.canonical_mnemonic,
            aliases=aliases,
            name_ru=value.name_ru,
            short_name_ru=value.name_ru,
            unit=value.unit,
            family=value.family,
            category=value.category,
            default_min=value.default_min,
            default_max=value.default_max,
            color=value.color,
            source="Пользовательский словарь",
        )


class UserMnemonicRegistry:
    SETTINGS_KEY = "mnemonics/user_rules_v1"

    def __init__(self, settings: Any | None = None) -> None:
        self.settings = settings or QSettings()

    def rules(self) -> tuple[UserMnemonicRule, ...]:
        raw = self.settings.value(self.SETTINGS_KEY, "[]")
        try:
            payload = json.loads(str(raw))
        except json.JSONDecodeError:
            return ()
        if not isinstance(payload, list):
            return ()
        result: list[UserMnemonicRule] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            try:
                aliases = row.get("aliases", [])
                row = dict(row)
                row["aliases"] = tuple(str(x) for x in aliases) if isinstance(aliases, list) else ()
                result.append(UserMnemonicRule(**row).validate())
            except (TypeError, ValueError):
                continue
        return tuple(result)

    def save(self, rules: Iterable[UserMnemonicRule]) -> None:
        validated = tuple(rule.validate() for rule in rules)
        keys: set[str] = set()
        for rule in validated:
            key = rule.foreign_mnemonic.strip().casefold()
            if key in keys:
                raise ValueError(f"Повторяющееся правило для мнемоники: {rule.foreign_mnemonic}")
            keys.add(key)
        self.settings.setValue(
            self.SETTINGS_KEY,
            json.dumps([asdict(rule) for rule in validated], ensure_ascii=False),
        )
        self.settings.sync()

    def upsert(self, rule: UserMnemonicRule) -> UserMnemonicRule:
        value = rule.validate()
        rows = list(self.rules())
        for index, current in enumerate(rows):
            if current.rule_id == value.rule_id:
                rows[index] = value
                break
        else:
            rows.append(value)
        self.save(rows)
        return value

    def delete(self, rule_id: str) -> None:
        rows = tuple(rule for rule in self.rules() if rule.rule_id != rule_id)
        self.save(rows)

    def export_json(self, path: str | Path) -> None:
        payload = {"schema_version": 1, "rules": [asdict(rule) for rule in self.rules()]}
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def import_json(self, path: str | Path, *, merge: bool = True) -> None:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Неподдерживаемый формат словаря мнемоник")
        rows = payload.get("rules")
        if not isinstance(rows, list):
            raise ValueError("В словаре отсутствует массив rules")
        imported: list[UserMnemonicRule] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            aliases = row.get("aliases", [])
            item = dict(row)
            item["aliases"] = tuple(str(x) for x in aliases) if isinstance(aliases, list) else ()
            imported.append(UserMnemonicRule(**item).validate())
        if merge:
            by_id = {rule.rule_id: rule for rule in self.rules()}
            by_id.update({rule.rule_id: rule for rule in imported})
            self.save(by_id.values())
        else:
            self.save(imported)

    def catalog(self, base: SensorCatalog | None = None) -> SensorCatalog:
        base_catalog = base or default_sensor_catalog()
        user_sensors = tuple(rule.to_sensor() for rule in self.rules())
        return SensorCatalog(
            (*user_sensors, *base_catalog.sensors),
            catalog_name=f"{base_catalog.catalog_name} + пользовательские правила",
            sources=("Пользовательский словарь", *base_catalog.sources),
        )
