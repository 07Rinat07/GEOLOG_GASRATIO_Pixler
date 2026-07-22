from __future__ import annotations

import os
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_MEDIA_TYPE = "image/png"
SVG_MEDIA_TYPE = "image/svg+xml"
MAX_IMAGE_ASSET_BYTES = 10 * 1024 * 1024

_SVG_ALLOWED_ELEMENTS = {
    "svg",
    "g",
    "defs",
    "title",
    "desc",
    "path",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "text",
    "tspan",
    "linearGradient",
    "radialGradient",
    "stop",
    "clipPath",
}
_SVG_FORBIDDEN_RAW = (b"<!doctype", b"<!entity")
_SVG_DANGEROUS_VALUE = re.compile(r"(?:javascript:|data:|@import)", re.IGNORECASE)
_SVG_URL_VALUE = re.compile(r"url\(\s*(['\"]?)([^)'\"]+)\1\s*\)", re.IGNORECASE)


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
    return ImageAsset(f"sha256:{digest}", source.name, PNG_MEDIA_TYPE, payload)



def create_raster_asset(source: Path) -> ImageAsset:
    """Create a normalized PNG asset from any raster format supported by Qt.

    This covers PNG, JPEG, BMP, TIFF and WebP when the corresponding Qt image
    plugin is available. Normalization keeps project serialization and print
    rendering deterministic.
    """

    if not source.is_file() or source.is_symlink():
        raise ImageAssetError("Raster asset должен быть обычным файлом")
    if source.stat().st_size > MAX_IMAGE_ASSET_BYTES:
        raise ImageAssetError("Raster asset превышает лимит 10 МБ")
    if source.suffix.casefold() == ".png":
        return create_png_asset(source)
    # Project loading, persistence and SVG/PNG validation are deliberately
    # independent of Qt.  Import Qt only for the operation that actually needs
    # its raster codecs so headless/domain tests remain usable.
    try:
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QImage
    except ModuleNotFoundError as exc:  # pragma: no cover - deployment guard
        raise ImageAssetError(
            "Для преобразования JPEG/BMP/TIFF/WebP требуется установленный PySide6"
        ) from exc
    image = QImage(str(source))
    if image.isNull():
        raise ImageAssetError("Формат изображения не поддерживается или файл повреждён")
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise ImageAssetError("Не удалось открыть буфер преобразования изображения")
    try:
        if not image.save(buffer, cast(Any, "PNG")):
            raise ImageAssetError("Не удалось преобразовать изображение в PNG")
        payload = bytes(buffer.data().data())
    finally:
        buffer.close()
    digest = sha256(payload).hexdigest()
    return ImageAsset(f"sha256:{digest}", source.name, PNG_MEDIA_TYPE, payload)

def create_svg_asset(source: Path) -> ImageAsset:
    if not source.is_file() or source.is_symlink():
        raise ImageAssetError("SVG asset должен быть обычным файлом")
    if source.stat().st_size > MAX_IMAGE_ASSET_BYTES:
        raise ImageAssetError("SVG asset превышает лимит 10 МБ")
    payload = source.read_bytes()
    _validate_svg_payload(payload)
    digest = sha256(payload).hexdigest()
    return ImageAsset(f"sha256:{digest}", source.name, SVG_MEDIA_TYPE, payload)


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
        target = directory / f"{digest}{_extension(asset.media_type)}"
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
            or raw.get("media_type") not in {PNG_MEDIA_TYPE, SVG_MEDIA_TYPE}
        ):
            raise ImageAssetError("Описание image asset некорректно")
        relative = Path(path)
        target = (project_path.parent / relative).resolve(strict=False)
        if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(directory):
            raise ImageAssetError("Image asset находится вне каталога проекта")
        if not target.is_file() or target.is_symlink():
            raise ImageAssetError(f"Image asset не найден: {relative}")
        payload = target.read_bytes()
        media_type = str(raw["media_type"])
        if target.suffix.casefold() != _extension(media_type):
            raise ImageAssetError("Расширение image asset не соответствует media_type")
        asset = ImageAsset(asset_id, name, media_type, payload)
        if len(payload) != size or sha256(payload).hexdigest() != digest:
            raise ImageAssetError(f"Image asset повреждён: {relative}")
        _validate_asset(asset_id, asset)
        assets[asset_id] = asset
    return assets


def _validate_asset(asset_id: str, asset: ImageAsset) -> None:
    digest = sha256(asset.payload).hexdigest()
    if asset_id != asset.asset_id or asset_id != f"sha256:{digest}":
        raise ImageAssetError("ID image asset не соответствует SHA-256 содержимого")
    if asset.media_type == PNG_MEDIA_TYPE:
        if not asset.payload.startswith(PNG_SIGNATURE):
            raise ImageAssetError("Файл не имеет корректной PNG-сигнатуры")
    elif asset.media_type == SVG_MEDIA_TYPE:
        _validate_svg_payload(asset.payload)
    else:
        raise ImageAssetError("Поддерживаются только проверенные PNG и SVG assets")
    if len(asset.payload) > MAX_IMAGE_ASSET_BYTES:
        raise ImageAssetError("Image asset превышает лимит 10 МБ")


def validate_image_asset(asset_id: str, asset: ImageAsset) -> None:
    _validate_asset(asset_id, asset)


def _asset_directory(project_path: Path) -> Path:
    return project_path.parent / f"{project_path.name}.assets" / "images"


def _remove_orphaned_assets(directory: Path, live_asset_ids: set[str]) -> None:
    live_names = set()
    for asset_id in live_asset_ids:
        digest = asset_id.removeprefix("sha256:")
        live_names.update({f"{digest}.png", f"{digest}.svg"})
    for candidate in directory.iterdir():
        if (
            candidate.name not in live_names
            and re.fullmatch(r"[0-9a-f]{64}\.(?:png|svg)", candidate.name)
            and candidate.is_file()
            and not candidate.is_symlink()
        ):
            candidate.unlink()


def _extension(media_type: str) -> str:
    return ".svg" if media_type == SVG_MEDIA_TYPE else ".png"


def _validate_svg_payload(payload: bytes) -> None:
    if not payload or any(marker in payload.lower() for marker in _SVG_FORBIDDEN_RAW):
        raise ImageAssetError("SVG содержит запрещённые DTD или entities")
    try:
        root = ET.fromstring(payload)
    except (ET.ParseError, ValueError) as exc:
        raise ImageAssetError("SVG имеет некорректную XML-структуру") from exc
    if _local_name(root.tag) != "svg":
        raise ImageAssetError("Корневой элемент SVG должен быть <svg>")
    for element in root.iter():
        if _local_name(element.tag) not in _SVG_ALLOWED_ELEMENTS:
            raise ImageAssetError(f"SVG содержит запрещённый элемент: {_local_name(element.tag)}")
        for raw_name, value in element.attrib.items():
            name = _local_name(raw_name).casefold()
            if name.startswith("on") or name in {"href", "src"}:
                raise ImageAssetError("SVG содержит ссылки или обработчики событий")
            if _SVG_DANGEROUS_VALUE.search(value):
                raise ImageAssetError("SVG содержит небезопасное значение атрибута")
            for match in _SVG_URL_VALUE.finditer(value):
                if not match.group(2).strip().startswith("#"):
                    raise ImageAssetError("SVG содержит внешнюю ссылку")


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


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
