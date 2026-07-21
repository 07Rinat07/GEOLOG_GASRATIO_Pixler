from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


SUPPORTED_SCHEMA = "geoworkbench.constructor-assets/v1"


@dataclass(frozen=True, slots=True)
class LocalizedName:
    ru: str
    kk: str
    en: str

    def for_language(self, language: str) -> str:
        normalized = str(language).strip().lower().replace("_", "-")
        if normalized.startswith("kk"):
            return self.kk or self.ru or self.en
        if normalized.startswith("en"):
            return self.en or self.ru or self.kk
        return self.ru or self.kk or self.en


@dataclass(frozen=True, slots=True)
class AssetDefinition:
    asset_id: str
    kind: str
    name: LocalizedName
    aliases: tuple[str, ...]
    category: str
    asset_path: Path
    thumbnail_path: Path | None
    width_px: int
    height_px: int
    content_sha256: str
    properties: Mapping[str, object]
    active: bool = True

    def display_name(self, language: str = "ru") -> str:
        return self.name.for_language(language)

    def search_tokens(self) -> tuple[str, ...]:
        values = {
            self.asset_id,
            self.category,
            self.name.ru,
            self.name.kk,
            self.name.en,
            *self.aliases,
        }
        return tuple(sorted({value.casefold() for value in values if value}))


class ConstructorAssetRegistry:
    """Read-only registry for factory lithotypes and depth symbols.

    The registry keeps asset paths relative to the manifest directory, validates
    duplicate IDs and exposes deterministic search.  User assets will be layered on
    top of this registry in a later persistence slice.
    """

    def __init__(self, assets: Iterable[AssetDefinition] = ()) -> None:
        self._assets: dict[str, AssetDefinition] = {}
        for asset in assets:
            self.add(asset)

    def add(self, asset: AssetDefinition) -> None:
        if not asset.asset_id:
            raise ValueError("asset_id must not be empty")
        if asset.asset_id in self._assets:
            raise ValueError(f"duplicate constructor asset id: {asset.asset_id}")
        if asset.width_px <= 0 or asset.height_px <= 0:
            raise ValueError(f"invalid image dimensions for {asset.asset_id}")
        self._assets[asset.asset_id] = asset

    def __len__(self) -> int:
        return len(self._assets)

    def __iter__(self):
        return iter(self.all())

    def get(self, asset_id: str) -> AssetDefinition:
        try:
            return self._assets[asset_id]
        except KeyError as exc:
            raise KeyError(f"unknown constructor asset: {asset_id}") from exc

    def all(self, *, kind: str | None = None, active_only: bool = True) -> tuple[AssetDefinition, ...]:
        values = self._assets.values()
        if kind is not None:
            values = (asset for asset in values if asset.kind == kind)
        if active_only:
            values = (asset for asset in values if asset.active)
        return tuple(sorted(values, key=lambda asset: (asset.kind, asset.category, asset.asset_id)))

    def search(
        self,
        query: str,
        *,
        kind: str | None = None,
        language: str = "ru",
        active_only: bool = True,
    ) -> tuple[AssetDefinition, ...]:
        needle = query.strip().casefold()
        candidates = self.all(kind=kind, active_only=active_only)
        if not needle:
            return candidates
        ranked: list[tuple[int, str, AssetDefinition]] = []
        for asset in candidates:
            display = asset.display_name(language).casefold()
            tokens = asset.search_tokens()
            if display == needle or asset.asset_id.casefold() == needle:
                score = 0
            elif display.startswith(needle) or any(token.startswith(needle) for token in tokens):
                score = 1
            elif needle in display or any(needle in token for token in tokens):
                score = 2
            else:
                continue
            ranked.append((score, display, asset))
        return tuple(asset for _, _, asset in sorted(ranked, key=lambda row: (row[0], row[1], row[2].asset_id)))

    @classmethod
    def from_manifest(cls, manifest_path: str | Path) -> "ConstructorAssetRegistry":
        path = Path(manifest_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != SUPPORTED_SCHEMA:
            raise ValueError(f"unsupported constructor asset schema in {path}")
        root = path.parent.parent
        assets = []
        for raw in payload.get("assets", []):
            name = raw.get("name", {})
            thumbnail_value = raw.get("thumbnail_path")
            properties = raw.get("render") or raw.get("placement") or {}
            assets.append(AssetDefinition(
                asset_id=str(raw["id"]),
                kind=str(raw["kind"]),
                name=LocalizedName(
                    ru=str(name.get("ru", "")),
                    kk=str(name.get("kk", "")),
                    en=str(name.get("en", "")),
                ),
                aliases=tuple(str(value) for value in raw.get("aliases", [])),
                category=str(raw.get("category", "unclassified")),
                asset_path=(root / str(raw["asset_path"])).resolve(),
                thumbnail_path=(root / str(thumbnail_value)).resolve() if thumbnail_value else None,
                width_px=int(raw["width_px"]),
                height_px=int(raw["height_px"]),
                content_sha256=str(raw["content_sha256"]),
                properties=dict(properties),
                active=bool(raw.get("active", True)),
            ))
        return cls(assets)

    @classmethod
    def from_root(cls, asset_root: str | Path) -> "ConstructorAssetRegistry":
        root = Path(asset_root)
        merged = cls()
        for relative in (Path("lithology/manifest.json"), Path("symbols/manifest.json")):
            manifest = root / relative
            if not manifest.exists():
                continue
            for asset in cls.from_manifest(manifest):
                merged.add(asset)
        return merged

    def validate_files(self) -> tuple[str, ...]:
        errors: list[str] = []
        for asset in self.all(active_only=False):
            if not asset.asset_path.is_file():
                errors.append(f"missing asset file: {asset.asset_id}: {asset.asset_path}")
            else:
                digest = hashlib.sha256(asset.asset_path.read_bytes()).hexdigest()
                if digest != asset.content_sha256:
                    errors.append(
                        f"asset checksum mismatch: {asset.asset_id}: "
                        f"expected {asset.content_sha256}, got {digest}"
                    )
            if asset.thumbnail_path is not None and not asset.thumbnail_path.is_file():
                errors.append(f"missing thumbnail: {asset.asset_id}: {asset.thumbnail_path}")
        return tuple(errors)
