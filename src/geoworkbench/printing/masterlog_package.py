from __future__ import annotations

import base64
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from geoworkbench.domain.models import (
    MasterlogColumnTemplate,
    MasterlogCurveStyle,
    MasterlogHeaderElement,
    MasterlogTemplate,
)
from geoworkbench.printing.image_assets import (
    ImageAsset,
    ImageAssetError,
    validate_image_asset,
)
from geoworkbench.project.session import ProjectSession


MASTERLOG_PACKAGE_VERSION = 2
SUPPORTED_MASTERLOG_PACKAGE_VERSIONS = {1, MASTERLOG_PACKAGE_VERSION}
MAX_MASTERLOG_PACKAGE_BYTES = 25 * 1024 * 1024


class MasterlogPackageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MasterlogPackage:
    template: MasterlogTemplate
    image_assets: dict[str, ImageAsset]


def export_masterlog_package(
    template: MasterlogTemplate,
    session: ProjectSession,
    target: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != ".json":
        raise MasterlogPackageError("Пакет masterlog должен иметь расширение .json")
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    referenced = {
        asset_ref
        for element in template.header_elements
        if element.element_type == "image"
        and isinstance((asset_ref := element.properties.get("asset_ref")), str)
    }
    missing = referenced - set(session.image_assets)
    if missing:
        raise MasterlogPackageError(
            "Пакет содержит отсутствующие image assets: " + ", ".join(sorted(missing))
        )
    assets: dict[str, Any] = {}
    for asset_id in sorted(referenced):
        asset = session.image_assets[asset_id]
        try:
            validate_image_asset(asset_id, asset)
        except ImageAssetError as exc:
            raise MasterlogPackageError(str(exc)) from exc
        assets[asset_id] = {
            "original_name": asset.original_name,
            "media_type": asset.media_type,
            "payload_base64": base64.b64encode(asset.payload).decode("ascii"),
        }
    payload = json.dumps(
        {
            "package_version": MASTERLOG_PACKAGE_VERSION,
            "template": asdict(template),
            "image_assets": assets,
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    if len(payload) > MAX_MASTERLOG_PACKAGE_BYTES:
        raise MasterlogPackageError("Пакет masterlog превышает лимит 25 МБ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise MasterlogPackageError(f"Не удалось экспортировать пакет: {destination}") from exc
    return destination


def load_masterlog_package(source: str | Path) -> MasterlogPackage:
    path = Path(source)
    if not path.is_file() or path.is_symlink():
        raise MasterlogPackageError("Пакет masterlog должен быть обычным файлом")
    if path.stat().st_size > MAX_MASTERLOG_PACKAGE_BYTES:
        raise MasterlogPackageError("Пакет masterlog превышает лимит 25 МБ")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MasterlogPackageError("Не удалось прочитать пакет masterlog") from exc
    package_version = raw.get("package_version") if isinstance(raw, dict) else None
    if (
        not isinstance(package_version, int)
        or isinstance(package_version, bool)
        or package_version not in SUPPORTED_MASTERLOG_PACKAGE_VERSIONS
    ):
        raise MasterlogPackageError("Версия пакета masterlog не поддерживается")
    template = _template_from_dict(raw.get("template"))
    assets = _assets_from_dict(raw.get("image_assets"), package_version)
    referenced = {
        asset_ref
        for element in template.header_elements
        if element.element_type == "image"
        and isinstance((asset_ref := element.properties.get("asset_ref")), str)
    }
    if referenced - set(assets):
        raise MasterlogPackageError("Пакет masterlog не содержит все связанные image assets")
    return MasterlogPackage(template, assets)


def _template_from_dict(raw: object) -> MasterlogTemplate:
    if not isinstance(raw, dict):
        raise MasterlogPackageError("Пакет не содержит шаблон masterlog")
    try:
        elements_raw = raw.get("header_elements", [])
        columns_raw = raw.get("columns", [])
        if not isinstance(elements_raw, list) or not isinstance(columns_raw, list):
            raise TypeError
        data = dict(raw)
        data["header_elements"] = [MasterlogHeaderElement(**item) for item in elements_raw]
        columns: list[MasterlogColumnTemplate] = []
        for item in columns_raw:
            if not isinstance(item, dict):
                raise TypeError
            column_data = dict(item)
            raw_styles = column_data.get("curve_styles", {})
            if not isinstance(raw_styles, dict):
                raise TypeError
            column_data["curve_styles"] = {
                str(mnemonic): MasterlogCurveStyle(**style)
                for mnemonic, style in raw_styles.items()
                if isinstance(style, dict)
            }
            if len(column_data["curve_styles"]) != len(raw_styles):
                raise TypeError
            columns.append(MasterlogColumnTemplate(**column_data))
        data["columns"] = columns
        return MasterlogTemplate(**data)
    except (TypeError, ValueError) as exc:
        raise MasterlogPackageError("Шаблон в пакете masterlog некорректен") from exc


def _assets_from_dict(raw: object, package_version: int) -> dict[str, ImageAsset]:
    if not isinstance(raw, dict):
        raise MasterlogPackageError("Поле image_assets пакета должно быть объектом")
    assets: dict[str, ImageAsset] = {}
    for asset_id, item in raw.items():
        if not isinstance(asset_id, str) or not isinstance(item, dict):
            raise MasterlogPackageError("Запись image asset в пакете некорректна")
        name = item.get("original_name")
        encoded = item.get("payload_base64")
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 255
            or "/" in name
            or "\\" in name
            or any(ord(character) < 32 for character in name)
            or item.get("media_type") not in {"image/png", "image/svg+xml"}
            or not isinstance(encoded, str)
        ):
            raise MasterlogPackageError("Метаданные image asset в пакете некорректны")
        media_type = str(item["media_type"])
        if package_version == 1 and media_type != "image/png":
            raise MasterlogPackageError("Пакет masterlog v1 поддерживает только PNG assets")
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise MasterlogPackageError("Image asset содержит некорректный base64") from exc
        asset = ImageAsset(asset_id, name, media_type, payload)
        try:
            validate_image_asset(asset_id, asset)
        except ImageAssetError as exc:
            raise MasterlogPackageError(str(exc)) from exc
        assets[asset_id] = asset
    return assets
