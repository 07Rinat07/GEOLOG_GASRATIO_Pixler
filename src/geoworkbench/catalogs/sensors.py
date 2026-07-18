from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
import json
from pathlib import Path
import re
from typing import Any, Iterable


_VALID_CATEGORIES = {"gas", "drilling", "mud", "petrophysics", "dexp", "other"}
_VALID_FAMILIES = {
    "gas",
    "rop",
    "rotary_speed",
    "wob",
    "torque",
    "pressure",
    "hookload",
    "flow",
    "drilling_depth",
    "mud_density",
    "temperature",
    "pit_volume",
    "conductivity",
    "chlorides",
    "gamma_ray",
    "sp",
    "caliper",
    "bulk_density",
    "neutron",
    "sonic",
    "resistivity",
    "pef",
    "dexp",
    "other",
}
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
_NON_ALNUM = re.compile(r"[^0-9A-ZА-ЯЁ]+")
_CONFUSABLES = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "С": "C",
        "Е": "E",
        "Н": "H",
        "К": "K",
        "М": "M",
        "О": "O",
        "Р": "P",
        "Т": "T",
        "Х": "X",
        "У": "Y",
    }
)


def normalize_sensor_key(value: str) -> str:
    """Normalize LAS mnemonic/reference labels for deterministic matching.

    Legacy Russian databases sometimes contain visually identical Cyrillic letters in
    Latin mnemonics (for example ``С1`` instead of ``C1``). The transliteration is
    intentionally limited to common homoglyphs so that normal Russian descriptions
    remain searchable too.
    """

    normalized = value.strip().upper().replace("Ё", "Е").translate(_CONFUSABLES)
    return _NON_ALNUM.sub("", normalized)


def normalize_unit(value: str) -> str:
    normalized = value.strip().casefold().replace("³", "3").replace("²", "2")
    normalized = normalized.replace(" ", "").replace("°", "")
    aliases = {
        "meter": "m",
        "metre": "m",
        "м": "m",
        "м/час": "m/h",
        "м/ч": "m/h",
        "м3/ч": "m3/h",
        "л/с": "l/s",
        "г/см3": "g/cm3",
        "кг/м3": "kg/m3",
        "атм": "atm",
        "мпа": "mpa",
        "град": "deg",
    }
    return aliases.get(normalized, normalized)


@dataclass(frozen=True, slots=True)
class SensorDefinition:
    sensor_id: str
    canonical_mnemonic: str
    aliases: tuple[str, ...]
    name_ru: str
    short_name_ru: str
    unit: str
    family: str
    category: str
    default_min: float | None
    default_max: float | None
    color: str
    source: str
    legacy_gid: int | None = None
    legacy_table: str | None = None
    legacy_number: int | None = None

    @property
    def default_range_text(self) -> str:
        if self.default_min is None or self.default_max is None:
            return "—"
        return f"{self.default_min:g} … {self.default_max:g}"


@dataclass(frozen=True, slots=True)
class SensorMatch:
    definition: SensorDefinition
    matched_by: str
    confidence: float


class SensorCatalog:
    """Validated, immutable sensor/mnemonic reference catalog."""

    def __init__(
        self,
        sensors: Iterable[SensorDefinition],
        *,
        catalog_name: str,
        sources: Iterable[str] = (),
    ) -> None:
        definitions = tuple(sensors)
        if not definitions:
            raise ValueError("Справочник Sensors не содержит записей")
        self.catalog_name = catalog_name.strip() or "Sensors"
        self.sources = tuple(str(item) for item in sources)
        self.sensors = definitions
        self._by_id = {item.sensor_id: item for item in definitions}
        if len(self._by_id) != len(definitions):
            raise ValueError("В справочнике Sensors обнаружены повторяющиеся ID")

        alias_index: dict[str, list[SensorDefinition]] = {}
        description_index: dict[str, list[SensorDefinition]] = {}
        for item in definitions:
            for value in (item.canonical_mnemonic, *item.aliases):
                key = normalize_sensor_key(value)
                if key:
                    alias_index.setdefault(key, []).append(item)
            for value in (item.name_ru, item.short_name_ru):
                key = normalize_sensor_key(value)
                if key:
                    description_index.setdefault(key, []).append(item)
        self._alias_index = {key: tuple(value) for key, value in alias_index.items()}
        self._description_index = {
            key: tuple(value) for key, value in description_index.items()
        }

    @classmethod
    def from_json(cls, source: str | Path | dict[str, Any]) -> SensorCatalog:
        if isinstance(source, dict):
            payload = source
        else:
            path = Path(source)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"Не удалось прочитать справочник Sensors: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Корень справочника Sensors должен быть объектом JSON")
        schema_version = payload.get("schema_version")
        if schema_version != 1:
            raise ValueError(f"Неподдерживаемая версия справочника Sensors: {schema_version!r}")
        rows: list[dict[str, Any]] = []
        for section in ("sensors", "legacy_fields"):
            value = payload.get(section, [])
            if not isinstance(value, list):
                raise ValueError(f"Раздел {section} должен быть массивом")
            rows.extend(item for item in value if isinstance(item, dict))
        definitions = tuple(_definition_from_mapping(item) for item in rows)
        raw_sources = payload.get("sources", [])
        sources = (
            tuple(str(item) for item in raw_sources)
            if isinstance(raw_sources, list)
            else (str(raw_sources),)
        )
        return cls(
            definitions,
            catalog_name=str(payload.get("catalog_name") or "Sensors"),
            sources=sources,
        )

    def definition(self, sensor_id: str) -> SensorDefinition:
        try:
            return self._by_id[sensor_id]
        except KeyError as exc:
            raise KeyError(f"Параметр справочника не найден: {sensor_id}") from exc

    def match(
        self,
        mnemonic: str,
        *,
        description: str = "",
        unit: str = "",
    ) -> SensorMatch | None:
        mnemonic_key = normalize_sensor_key(mnemonic)
        exact = self._alias_index.get(mnemonic_key, ()) if mnemonic_key else ()
        if exact:
            selected = _choose_candidate(exact, unit=unit)
            return SensorMatch(selected, "mnemonic", 1.0)

        description_key = normalize_sensor_key(description)
        description_matches = (
            self._description_index.get(description_key, ()) if description_key else ()
        )
        if description_matches:
            selected = _choose_candidate(description_matches, unit=unit)
            return SensorMatch(selected, "description", 0.9)

        # A controlled fuzzy fallback is useful for LAS descriptions that add a prefix,
        # suffix or vendor note. Require a long token to avoid accidental matches such as
        # generic words "газ" or "глубина".
        if len(description_key) >= 8:
            candidates: list[tuple[int, SensorDefinition]] = []
            for key, items in self._description_index.items():
                if len(key) < 8:
                    continue
                if key in description_key or description_key in key:
                    for item in items:
                        candidates.append((min(len(key), len(description_key)), item))
            if candidates:
                candidates.sort(key=lambda row: (-row[0], row[1].sensor_id))
                best_length = candidates[0][0]
                best = [item for length, item in candidates if length == best_length]
                return SensorMatch(_choose_candidate(best, unit=unit), "description_fuzzy", 0.72)
        return None

    def search(self, text: str) -> tuple[SensorDefinition, ...]:
        needle = normalize_sensor_key(text)
        if not needle:
            return self.sensors
        result = [
            item
            for item in self.sensors
            if any(
                needle in normalize_sensor_key(value)
                for value in (
                    item.canonical_mnemonic,
                    item.name_ru,
                    item.short_name_ru,
                    item.unit,
                    *item.aliases,
                )
            )
        ]
        return tuple(result)


def _definition_from_mapping(raw: dict[str, Any]) -> SensorDefinition:
    sensor_id = str(raw.get("id") or "").strip()
    canonical = str(raw.get("canonical_mnemonic") or "").strip().upper()
    if not sensor_id or not canonical:
        raise ValueError("Запись Sensors должна содержать id и canonical_mnemonic")
    aliases_raw = raw.get("aliases", [])
    aliases = tuple(str(item).strip() for item in aliases_raw if str(item).strip())
    family = str(raw.get("family") or "other").strip()
    category = str(raw.get("category") or "other").strip()
    if family not in _VALID_FAMILIES:
        raise ValueError(f"Неизвестное семейство Sensors: {family}")
    if category not in _VALID_CATEGORIES:
        raise ValueError(f"Неизвестная категория Sensors: {category}")
    color = str(raw.get("color") or "#000000").strip().lower()
    if not _HEX_COLOR.fullmatch(color):
        raise ValueError(f"Некорректный цвет Sensors: {color}")
    default_min = _optional_float(raw.get("default_min"))
    default_max = _optional_float(raw.get("default_max"))
    if default_min is not None and default_max is not None and default_min > default_max:
        default_min, default_max = default_max, default_min
    return SensorDefinition(
        sensor_id=sensor_id,
        canonical_mnemonic=canonical,
        aliases=aliases,
        name_ru=str(raw.get("name_ru") or canonical).strip(),
        short_name_ru=str(raw.get("short_name_ru") or raw.get("name_ru") or canonical).strip(),
        unit=str(raw.get("unit") or "").strip(),
        family=family,
        category=category,
        default_min=default_min,
        default_max=default_max,
        color=color,
        source=str(raw.get("source") or "").strip(),
        legacy_gid=_optional_int(raw.get("legacy_gid")),
        legacy_table=_optional_text(raw.get("legacy_table")),
        legacy_number=_optional_int(raw.get("legacy_number")),
    )


def _choose_candidate(
    candidates: Iterable[SensorDefinition], *, unit: str
) -> SensorDefinition:
    values = tuple(candidates)
    requested_unit = normalize_unit(unit)
    if requested_unit:
        same_unit = [item for item in values if normalize_unit(item.unit) == requested_unit]
        if same_unit:
            values = tuple(same_unit)
    # Prefer the primary Editor/Sensors entries over secondary legacy table fields.
    return min(
        values,
        key=lambda item: (
            1 if item.legacy_table else 0,
            1 if item.canonical_mnemonic.startswith("SENSOR_") else 0,
            item.sensor_id,
        ),
    )


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Ожидалось число в справочнике Sensors: {value!r}") from exc


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Ожидалось целое число в справочнике Sensors: {value!r}") from exc


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value not in (None, "") else ""
    return text or None


_active_sensor_catalog: SensorCatalog | None = None


def set_active_sensor_catalog(catalog: SensorCatalog | None) -> None:
    global _active_sensor_catalog
    _active_sensor_catalog = catalog


def active_sensor_catalog() -> SensorCatalog:
    return _active_sensor_catalog or default_sensor_catalog()


@lru_cache(maxsize=1)
def default_sensor_catalog() -> SensorCatalog:
    resource = resources.files("geoworkbench").joinpath("resources/sensors.ru.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return SensorCatalog.from_json(payload)
