from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_IMAGE_ASSET_BYTES = 10 * 1024 * 1024


class ImageAssetError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ImageAsset:
    asset_id: str
    original_name: str
    media_type: str
    payload: bytes


def create_png_asset(source: Path) -> ImageAsset:
    if not source.is_file() or source.is_symlink():
        raise ImageAssetError("PNG asset должен быть обычным файлом")
    if source.stat().st_size > MAX_IMAGE_ASSET_BYTES:
        raise ImageAssetError("PNG asset превышает лимит 10 МБ")
    payload = source.read_bytes()
    if not payload.startswith(PNG_SIGNATURE):
        raise ImageAssetError("Файл не имеет корректной PNG-сигнатуры")
    digest = sha256(payload).hexdigest()
    return ImageAsset(f"sha256:{digest}", source.name, "image/png", payload)


def save_image_assets(project_path: Path, assets: dict[str, ImageAsset]) -> dict[str, Any]:
    directory = _asset_directory(project_path)
    if directory.is_symlink():
        raise ImageAssetError("Каталог image assets не может быть символической ссылкой")
    if assets:
        directory.mkdir(parents=True, exist_ok=True)
    elif not directory.exists():
        return {}
    if not directory.is_dir():
        raise ImageAssetError("Путь image assets должен быть каталогом")
    manifest: dict[str, Any] = {}
    for asset_id, asset in assets.items():
        _validate_asset(asset_id, asset)
        digest = asset_id.removeprefix("sha256:")
        target = directory / f"{digest}.png"
        if target.exists():
            if target.is_symlink() or target.read_bytes() != asset.payload:
                raise ImageAssetError(f"Существующий image asset повреждён: {target.name}")
        else:
            _atomic_write(target, asset.payload)
        manifest[asset_id] = {
            "path": target.relative_to(project_path.parent).as_posix(),
            "sha256": digest,
            "size_bytes": len(asset.payload),
            "media_type": asset.media_type,
            "original_name": asset.original_name,
        }
    _remove_orphaned_assets(directory, set(manifest))
    return manifest


def load_image_assets(project_path: Path, manifest: Any) -> dict[str, ImageAsset]:
    if not isinstance(manifest, dict):
        raise ImageAssetError("Поле image_assets должно быть объектом")
    raw_directory = _asset_directory(project_path)
    if raw_directory.is_symlink():
        raise ImageAssetError("Каталог image assets не может быть символической ссылкой")
    directory = raw_directory.resolve(strict=False)
    assets: dict[str, ImageAsset] = {}
    for asset_id, raw in manifest.items():
        if not isinstance(asset_id, str) or not isinstance(raw, dict):
            raise ImageAssetError("Запись image asset имеет неверный формат")
        path = raw.get("path")
        digest = raw.get("sha256")
        size = raw.get("size_bytes")
        name = raw.get("original_name")
        if (
            not isinstance(path, str)
            or not isinstance(digest, str)
            or asset_id != f"sha256:{digest}"
            or not isinstance(size, int)
            or isinstance(size, bool)
            or not isinstance(name, str)
            or raw.get("media_type") != "image/png"
        ):
            raise ImageAssetError("Описание image asset некорректно")
        relative = Path(path)
        target = (project_path.parent / relative).resolve(strict=False)
        if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(directory):
            raise ImageAssetError("Image asset находится вне каталога проекта")
        if not target.is_file() or target.is_symlink():
            raise ImageAssetError(f"Image asset не найден: {relative}")
        payload = target.read_bytes()
        asset = ImageAsset(asset_id, name, "image/png", payload)
        if len(payload) != size or sha256(payload).hexdigest() != digest:
            raise ImageAssetError(f"Image asset повреждён: {relative}")
        _validate_asset(asset_id, asset)
        assets[asset_id] = asset
    return assets


def _validate_asset(asset_id: str, asset: ImageAsset) -> None:
    digest = sha256(asset.payload).hexdigest()
    if asset_id != asset.asset_id or asset_id != f"sha256:{digest}":
        raise ImageAssetError("ID image asset не соответствует SHA-256 содержимого")
    if asset.media_type != "image/png" or not asset.payload.startswith(PNG_SIGNATURE):
        raise ImageAssetError("Поддерживаются только проверенные PNG assets")
    if len(asset.payload) > MAX_IMAGE_ASSET_BYTES:
        raise ImageAssetError("PNG asset превышает лимит 10 МБ")


def _asset_directory(project_path: Path) -> Path:
    return project_path.parent / f"{project_path.name}.assets" / "images"


def _remove_orphaned_assets(directory: Path, live_asset_ids: set[str]) -> None:
    live_names = {
        f"{asset_id.removeprefix('sha256:')}.png" for asset_id in live_asset_ids
    }
    for candidate in directory.iterdir():
        if (
            candidate.name not in live_names
            and re.fullmatch(r"[0-9a-f]{64}\.png", candidate.name)
            and candidate.is_file()
            and not candidate.is_symlink()
        ):
            candidate.unlink()


def _atomic_write(target: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, target)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
