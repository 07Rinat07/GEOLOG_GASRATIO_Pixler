from __future__ import annotations

from hashlib import sha256
from importlib.resources import files
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

from geoworkbench.domain.models import ProjectLithotype
from geoworkbench.form_constructor.asset_registry import AssetDefinition, ConstructorAssetRegistry
from geoworkbench.printing.image_assets import ImageAsset, PNG_MEDIA_TYPE
from geoworkbench.project.session import ProjectSession


CONSTRUCTOR_PATTERN_PREFIX = "constructor:"


def default_constructor_asset_root() -> Path:
    """Return the installed factory constructor asset directory.

    GEOLOG is distributed as an unpacked desktop application, therefore package
    resources are available as normal files. Keeping this resolver in one place
    also makes tests and future resource packaging easier to adapt.
    """

    return Path(str(files("geoworkbench").joinpath("resources/constructor_assets")))


@lru_cache(maxsize=1)
def load_factory_constructor_registry() -> ConstructorAssetRegistry:
    root = default_constructor_asset_root()
    registry = ConstructorAssetRegistry.from_root(root)
    errors = registry.validate_files()
    if errors:
        raise RuntimeError("\n".join(errors))
    return registry


def factory_asset_to_png(asset: AssetDefinition) -> ImageAsset:
    """Convert a legacy BMP/other Qt-readable resource into a portable PNG asset."""

    payload = _png_payload(str(asset.asset_path))
    digest = sha256(payload).hexdigest()
    return ImageAsset(
        asset_id=f"sha256:{digest}",
        original_name=f"{asset.display_name('ru')}.png",
        media_type=PNG_MEDIA_TYPE,
        payload=payload,
    )




@lru_cache(maxsize=256)
def _png_payload(asset_path: str) -> bytes:
    image = QImage(asset_path)
    if image.isNull():
        raise ValueError(f"Не удалось прочитать ресурс конструктора: {asset_path}")
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Не удалось открыть буфер PNG")
    try:
        if not image.save(buffer, cast(Any, "PNG")):
            raise RuntimeError(f"Не удалось преобразовать ресурс в PNG: {asset_path}")
        return bytes(buffer.data().data())
    finally:
        buffer.close()


def install_asset_into_project(
    session: ProjectSession,
    asset: AssetDefinition,
) -> tuple[ImageAsset, ProjectLithotype | None]:
    """Install one factory asset into the current project without duplication.

    Depth symbols become project image assets. Lithology patterns additionally
    become project lithotype definitions whose pattern key points back to the
    packaged tiled bitmap.
    """

    image_asset = factory_asset_to_png(asset)
    existing = session.image_assets.get(image_asset.asset_id)
    if existing is not None and existing.payload != image_asset.payload:
        raise ValueError(f"Конфликт графического ресурса: {asset.asset_id}")
    changed = existing is None
    if existing is None:
        session.image_assets[image_asset.asset_id] = image_asset

    lithotype: ProjectLithotype | None = None
    if asset.kind == "lithology_pattern":
        current = session.project.lithotypes.get(asset.asset_id)
        if current is None:
            lithotype = factory_asset_to_project_lithotype(asset)
            session.project.lithotypes[asset.asset_id] = lithotype
            changed = True
        else:
            lithotype = current
    if changed:
        session.dirty = True
    return image_asset, lithotype


def install_assets_into_project(
    session: ProjectSession,
    assets: tuple[AssetDefinition, ...] | list[AssetDefinition],
) -> tuple[int, int]:
    images_before = len(session.image_assets)
    lithotypes_before = len(session.project.lithotypes)
    for asset in assets:
        install_asset_into_project(session, asset)
    return (
        len(session.image_assets) - images_before,
        len(session.project.lithotypes) - lithotypes_before,
    )


def resolve_constructor_pattern_asset(pattern_key: str) -> AssetDefinition | None:
    if not pattern_key.startswith(CONSTRUCTOR_PATTERN_PREFIX):
        return None
    asset_id = pattern_key.removeprefix(CONSTRUCTOR_PATTERN_PREFIX)
    try:
        return load_factory_constructor_registry().get(asset_id)
    except (KeyError, OSError, RuntimeError, ValueError):
        return None


def factory_asset_to_project_lithotype(asset: AssetDefinition) -> ProjectLithotype:
    """Convert one packaged lithology bitmap into a project-compatible definition.

    This helper is intentionally side-effect free.  The lithotype catalog uses it
    to expose all packaged legacy patterns as a factory layer without copying 117
    records into every project.  ``install_asset_into_project`` uses the same
    conversion when the user explicitly creates a project override.
    """

    if asset.kind != "lithology_pattern":
        raise ValueError(f"Ресурс не является литотипом: {asset.asset_id}")
    return ProjectLithotype(
        lithotype_id=asset.asset_id,
        code=_lithotype_code(asset),
        name_ru=asset.name.ru or asset.asset_id,
        name_kk=asset.name.kk or asset.name.ru or asset.asset_id,
        name_en=asset.name.en or asset.name.ru or asset.asset_id,
        category=asset.category or "constructor",
        color="#f8fafc",
        pattern_key=f"{CONSTRUCTOR_PATTERN_PREFIX}{asset.asset_id}",
    )


def _lithotype_code(asset: AssetDefinition) -> str:
    for alias in asset.aliases:
        value = _normalise_lithotype_code(alias)
        if value and any(char.isalpha() for char in value):
            return value
    base = asset.asset_id.removeprefix("lithology-").replace("-", " ")
    words = [word for word in base.split() if word]
    if not words:
        return "LITH"
    if len(words) == 1:
        return _normalise_lithotype_code(words[0]) or "LITH"
    abbreviation = "".join(word[0] for word in words)
    return _normalise_lithotype_code(abbreviation) or "LITH"


def _normalise_lithotype_code(value: str) -> str:
    """Return a catalog-editable code accepted by the project validator."""

    candidate = value.strip().upper().replace(" ", "_")
    candidate = "".join(
        char
        for char in candidate
        if char == "_" or char == "-" or char.isdigit() or (char.isalpha() and char.upper() == char)
    )
    candidate = candidate.strip("_-")[:20]
    return candidate
