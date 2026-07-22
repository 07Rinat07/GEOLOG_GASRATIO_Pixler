from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.resources import files
import json
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ChannelDefinition:
    source: str
    mnemonic: str
    name_ru: str
    name_kk: str
    name_en: str
    unit: str = ""
    category: str = "unknown"

    def localized_name(self, language: str) -> str:
        return {
            "ru": self.name_ru,
            "kk": self.name_kk,
            "en": self.name_en,
        }.get(language, self.name_ru)


class GeoScapeChannelDictionary:
    """System mappings plus optional user overrides.

    Unknown Sxxx codes are intentionally not guessed.  The caller receives
    ``None`` and keeps the original source mnemonic and an empty unit.
    """

    def __init__(
        self,
        system: dict[str, ChannelDefinition],
        user: dict[str, ChannelDefinition] | None = None,
    ) -> None:
        self._system = {key.casefold(): value for key, value in system.items()}
        self._user = {key.casefold(): value for key, value in (user or {}).items()}

    @classmethod
    def load(cls, user_path: str | Path | None = None) -> "GeoScapeChannelDictionary":
        resource = files("geoworkbench").joinpath("resources", "geoscape_channels.json")
        system = _read_definitions(json.loads(resource.read_text(encoding="utf-8")))
        user: dict[str, ChannelDefinition] = {}
        if user_path is not None and Path(user_path).exists():
            user = _read_definitions(json.loads(Path(user_path).read_text(encoding="utf-8")))
        return cls(system, user)

    def resolve(self, source: str) -> ChannelDefinition | None:
        key = source.casefold()
        return self._user.get(key) or self._system.get(key)

    def set_user(self, definition: ChannelDefinition) -> None:
        self._user[definition.source.casefold()] = definition

    def remove_user(self, source: str) -> None:
        self._user.pop(source.casefold(), None)

    def export_user(self, target: str | Path) -> Path:
        destination = Path(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "channels": [
                asdict(item)
                for item in sorted(
                    self._user.values(),
                    key=lambda item: item.source.casefold(),
                )
            ],
        }
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(destination)
        return destination


def _read_definitions(payload: object) -> dict[str, ChannelDefinition]:
    if not isinstance(payload, dict) or not isinstance(payload.get("channels"), list):
        raise ValueError("Некорректный словарь каналов GeoScape")
    result: dict[str, ChannelDefinition] = {}
    for raw in payload["channels"]:
        if not isinstance(raw, dict):
            raise ValueError("Запись словаря каналов должна быть объектом")
        definition = ChannelDefinition(**raw)
        result[definition.source] = definition
    return result
