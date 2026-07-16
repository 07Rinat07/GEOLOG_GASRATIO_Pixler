from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files

from geoworkbench.printing.image_assets import (
    ImageAsset,
    ImageAssetError,
    SVG_MEDIA_TYPE,
    validate_image_asset,
)


@dataclass(frozen=True, slots=True)
class MasterlogSymbol:
    symbol_id: str
    name_key: str
    payload: bytes

    def create_asset(self, name: str) -> ImageAsset:
        digest = sha256(self.payload).hexdigest()
        return ImageAsset(f"sha256:{digest}", f"{name}.svg", SVG_MEDIA_TYPE, self.payload)


def _load_builtin_symbols() -> tuple[MasterlogSymbol, ...]:
    source = files("geoworkbench").joinpath("resources/masterlog-symbols.json")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Не удалось загрузить каталог обозначений masterlog") from exc
    if not isinstance(raw, dict) or raw.get("catalog_version") != 1:
        raise RuntimeError("Версия каталога обозначений masterlog не поддерживается")
    items = raw.get("symbols")
    if not isinstance(items, list):
        raise RuntimeError("Каталог обозначений masterlog имеет неверный формат")
    result: list[MasterlogSymbol] = []
    known_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("Запись обозначения masterlog имеет неверный формат")
        symbol_id = item.get("id")
        name_key = item.get("name_key")
        svg = item.get("svg")
        if (
            not isinstance(symbol_id, str)
            or not symbol_id
            or symbol_id in known_ids
            or not isinstance(name_key, str)
            or not name_key.startswith("masterlog_symbols.")
            or not isinstance(svg, str)
            or not svg
        ):
            raise RuntimeError("Метаданные обозначения masterlog некорректны")
        known_ids.add(symbol_id)
        symbol = MasterlogSymbol(symbol_id, name_key, svg.encode("utf-8"))
        try:
            asset = symbol.create_asset(symbol_id)
            validate_image_asset(asset.asset_id, asset)
        except ImageAssetError as exc:
            raise RuntimeError(f"SVG обозначения masterlog некорректен: {symbol_id}") from exc
        result.append(symbol)
    return tuple(result)


BUILTIN_MASTERLOG_SYMBOLS = _load_builtin_symbols()


def builtin_masterlog_symbol(symbol_id: str) -> MasterlogSymbol:
    try:
        return next(item for item in BUILTIN_MASTERLOG_SYMBOLS if item.symbol_id == symbol_id)
    except StopIteration as exc:
        raise KeyError(f"Встроенное обозначение masterlog не найдено: {symbol_id}") from exc
