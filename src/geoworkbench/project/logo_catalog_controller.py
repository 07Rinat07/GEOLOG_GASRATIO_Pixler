from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from geoworkbench.domain.models import LogoCatalogEntry, new_id
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.image_assets import (
    ImageAsset,
    create_raster_asset,
    create_svg_asset,
    validate_image_asset,
)
from geoworkbench.printing.logo_catalog import BUILTIN_LOGOS, builtin_logo_definition


@dataclass(frozen=True, slots=True)
class LogoCatalogItem:
    logo_id: str
    name: str
    asset_id: str
    category: str
    notes: str
    read_only: bool
    factory: bool


class LogoCatalogController:
    """Manage reusable logo metadata independently from raw image assets."""

    def __init__(self, session: ProjectSession) -> None:
        self.session = session

    def items(self, language: str = "ru") -> tuple[LogoCatalogItem, ...]:
        factory = tuple(
            LogoCatalogItem(
                logo_id=item.logo_id,
                name=item.name(language),
                asset_id=item.create_asset().asset_id,
                category=item.category(language),
                notes=item.notes(language),
                read_only=True,
                factory=True,
            )
            for item in BUILTIN_LOGOS
        )
        user = tuple(
            LogoCatalogItem(
                logo_id=item.logo_id,
                name=item.name,
                asset_id=item.asset_id,
                category=item.category,
                notes=item.notes,
                read_only=False,
                factory=False,
            )
            for item in sorted(
                self.session.project.logo_catalog.values(),
                key=lambda value: (value.category.casefold(), value.name.casefold()),
            )
        )
        return factory + user

    def create_from_file(
        self,
        source: Path,
        *,
        name: str | None = None,
        category: str = "",
        notes: str = "",
    ) -> LogoCatalogEntry:
        asset = (
            create_svg_asset(source)
            if source.suffix.casefold() == ".svg"
            else create_raster_asset(source)
        )
        self._install_asset(asset)
        return self.create_from_asset(
            asset,
            name=name or source.stem,
            category=category,
            notes=notes,
        )

    def create_from_asset(
        self,
        asset: ImageAsset,
        *,
        name: str,
        category: str = "",
        notes: str = "",
    ) -> LogoCatalogEntry:
        self._install_asset(asset)
        normalized = self._validate_unique_name(name)
        entry = LogoCatalogEntry(
            logo_id=new_id(),
            name=normalized,
            asset_id=asset.asset_id,
            category=category.strip(),
            notes=notes.strip(),
        )
        self.session.project.logo_catalog[entry.logo_id] = entry
        self.session.dirty = True
        return entry

    def copy_factory(self, logo_id: str, *, name: str | None = None) -> LogoCatalogEntry:
        definition = builtin_logo_definition(logo_id)
        asset = definition.create_asset()
        return self.create_from_asset(
            asset,
            name=name or definition.name("ru"),
            category=definition.category("ru"),
            notes=definition.notes("ru"),
        )

    def duplicate(self, logo_id: str, name: str) -> LogoCatalogEntry:
        source = self._require_user(logo_id)
        normalized = self._validate_unique_name(name)
        entry = replace(source, logo_id=new_id(), name=normalized, version=1)
        self.session.project.logo_catalog[entry.logo_id] = entry
        self.session.dirty = True
        return entry

    def update_metadata(
        self,
        logo_id: str,
        *,
        name: str,
        category: str = "",
        notes: str = "",
    ) -> LogoCatalogEntry:
        source = self._require_user(logo_id)
        normalized = self._validate_unique_name(name, exclude_id=logo_id)
        updated = replace(
            source,
            name=normalized,
            category=category.strip(),
            notes=notes.strip(),
            version=source.version + 1,
        )
        self.session.project.logo_catalog[logo_id] = updated
        self.session.dirty = True
        return updated

    def replace_image(self, logo_id: str, source: Path) -> LogoCatalogEntry:
        entry = self._require_user(logo_id)
        asset = (
            create_svg_asset(source)
            if source.suffix.casefold() == ".svg"
            else create_raster_asset(source)
        )
        self._install_asset(asset)
        updated = replace(entry, asset_id=asset.asset_id, version=entry.version + 1)
        self.session.project.logo_catalog[logo_id] = updated
        self.session.dirty = True
        return updated

    def delete(self, logo_id: str) -> LogoCatalogEntry:
        entry = self._require_user(logo_id)
        del self.session.project.logo_catalog[logo_id]
        self.session.dirty = True
        return entry

    def resolve_asset(self, logo_id: str, *, install: bool = True) -> ImageAsset:
        if logo_id.startswith("factory-"):
            asset = builtin_logo_definition(logo_id).create_asset()
            if install:
                self._install_asset(asset)
            return asset
        entry = self._require_user(logo_id)
        try:
            return self.session.image_assets[entry.asset_id]
        except KeyError as exc:
            raise ValueError(f"Image asset логотипа не найден: {entry.name}") from exc

    def item(self, logo_id: str, language: str = "ru") -> LogoCatalogItem:
        try:
            return next(item for item in self.items(language) if item.logo_id == logo_id)
        except StopIteration as exc:
            raise KeyError(logo_id) from exc

    def _install_asset(self, asset: ImageAsset) -> None:
        validate_image_asset(asset.asset_id, asset)
        existing = self.session.image_assets.get(asset.asset_id)
        if existing is not None and existing.payload != asset.payload:
            raise ValueError(f"Конфликт содержимого image asset: {asset.asset_id}")
        self.session.image_assets[asset.asset_id] = asset

    def _require_user(self, logo_id: str) -> LogoCatalogEntry:
        try:
            return self.session.project.logo_catalog[logo_id]
        except KeyError as exc:
            if logo_id.startswith("factory-"):
                raise ValueError("Заводской логотип нужно сначала скопировать") from exc
            raise KeyError(logo_id) from exc

    def _validate_unique_name(self, name: str, *, exclude_id: str | None = None) -> str:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Имя логотипа не может быть пустым")
        if len(normalized) > 160:
            raise ValueError("Имя логотипа не должно превышать 160 символов")
        existing = {
            item.name.casefold()
            for logo_id, item in self.session.project.logo_catalog.items()
            if logo_id != exclude_id
        }
        if normalized.casefold() in existing:
            raise ValueError(f"Логотип с именем '{normalized}' уже существует")
        return normalized
