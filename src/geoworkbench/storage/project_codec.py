"""Project codec v29 for supplier rock-profile revisions and source bindings.

The v28 decoder is frozen in ``project_codec_v28``. Version 29 adds two
project-document-level provenance ledgers while delegating all geological,
well, dataset and legacy migration semantics to the proven v28 layer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from geoworkbench.domain.models import Project
from geoworkbench.domain.rock_code_profiles import (
    RockCodeProfileRecord,
    RockCodeSourceBindingRecord,
)
from geoworkbench.services.rock_code_dictionary import (
    RockCodeDictionary,
    RockCodeDictionaryError,
)
from geoworkbench.storage import project_codec_v28 as _v28
from geoworkbench.storage.project_codec_v28 import ProjectFormatError


PROJECT_FORMAT_VERSION = 29
_MAX_PROFILE_REVISIONS = 10_000
_MAX_SOURCE_BINDINGS = 100_000
_PROFILE_KEYS = {"supplier_name", "profile_json", "profile_sha256"}
_BINDING_KEYS = {"source_sha256", "supplier_name", "profile_sha256"}


@dataclass(slots=True)
class ProjectDocument(_v28.ProjectDocument):
    """Current project document plus reproducible supplier-profile provenance."""

    rock_code_profiles: dict[str, RockCodeProfileRecord] = field(default_factory=dict)
    rock_code_source_bindings: dict[str, RockCodeSourceBindingRecord] = field(
        default_factory=dict
    )


def _require_exact_keys(data: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ProjectFormatError(f"{label} содержит неизвестные поля: {names}")


def _profile_record_from_dict(data: object) -> RockCodeProfileRecord:
    if not isinstance(data, dict):
        raise ProjectFormatError("Ревизия профиля кодов пород должна быть объектом")
    _require_exact_keys(data, _PROFILE_KEYS, "rock-code profile")
    try:
        record = RockCodeProfileRecord(**data)
        dictionary = RockCodeDictionary.from_json(record.profile_json)
    except (TypeError, ValueError, RockCodeDictionaryError) as exc:
        raise ProjectFormatError("Некорректная ревизия профиля кодов пород") from exc
    if dictionary.to_json() != record.profile_json:
        raise ProjectFormatError("profile_json должен использовать канонический формат")
    return record


def _binding_record_from_dict(data: object) -> RockCodeSourceBindingRecord:
    if not isinstance(data, dict):
        raise ProjectFormatError("Привязка источника к профилю должна быть объектом")
    _require_exact_keys(data, _BINDING_KEYS, "rock-code source binding")
    try:
        return RockCodeSourceBindingRecord(**data)
    except (TypeError, ValueError) as exc:
        raise ProjectFormatError("Некорректная привязка источника к профилю") from exc


def _profile_records(data: object) -> dict[str, RockCodeProfileRecord]:
    if not isinstance(data, dict) or len(data) > _MAX_PROFILE_REVISIONS:
        raise ProjectFormatError("rock_code_profiles должен быть ограниченным объектом")
    records: dict[str, RockCodeProfileRecord] = {}
    for digest, raw in data.items():
        if not isinstance(digest, str):
            raise ProjectFormatError("Ключ ревизии профиля должен быть строкой")
        record = _profile_record_from_dict(raw)
        if digest != record.profile_sha256:
            raise ProjectFormatError("Ключ профиля не совпадает с profile_sha256")
        records[digest] = record
    return records


def _source_bindings(
    data: object,
    profiles: dict[str, RockCodeProfileRecord],
) -> dict[str, RockCodeSourceBindingRecord]:
    if not isinstance(data, dict) or len(data) > _MAX_SOURCE_BINDINGS:
        raise ProjectFormatError("rock_code_source_bindings должен быть ограниченным объектом")
    records: dict[str, RockCodeSourceBindingRecord] = {}
    for digest, raw in data.items():
        if not isinstance(digest, str):
            raise ProjectFormatError("Ключ привязки источника должен быть строкой")
        record = _binding_record_from_dict(raw)
        if digest != record.source_sha256:
            raise ProjectFormatError("Ключ источника не совпадает с source_sha256")
        profile = profiles.get(record.profile_sha256)
        if profile is None:
            raise ProjectFormatError("Привязка источника ссылается на отсутствующий профиль")
        if profile.supplier_name != record.supplier_name:
            raise ProjectFormatError(
                "Поставщик привязки не совпадает с поставщиком ревизии профиля"
            )
        records[digest] = record
    return records


def _format_version(data: dict[str, Any]) -> int:
    version = data.get("format_version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ProjectFormatError("Некорректная версия формата проекта")
    if version > PROJECT_FORMAT_VERSION:
        raise ProjectFormatError(
            f"Версия проекта {version} новее поддерживаемой {PROJECT_FORMAT_VERSION}"
        )
    return version


def _legacy_payload(data: dict[str, Any], version: int) -> dict[str, Any]:
    if version < PROJECT_FORMAT_VERSION:
        return data
    legacy = dict(data)
    legacy.pop("rock_code_profiles", None)
    legacy.pop("rock_code_source_bindings", None)
    legacy["format_version"] = _v28.PROJECT_FORMAT_VERSION
    return legacy


def project_from_dict(data: dict[str, Any]) -> Project:
    """Decode project-owned entities; profile ledgers belong to ProjectDocument."""

    return _v28.project_from_dict(data)


def project_document_from_dict(data: dict[str, Any]) -> ProjectDocument:
    """Decode v1…v29 without guessing suppliers for pre-v29 projects."""

    version = _format_version(data)
    if version == PROJECT_FORMAT_VERSION:
        profiles = _profile_records(data.get("rock_code_profiles", {}))
        bindings = _source_bindings(data.get("rock_code_source_bindings", {}), profiles)
    else:
        profiles = {}
        bindings = {}

    legacy_document = _v28.project_document_from_dict(_legacy_payload(data, version))
    return ProjectDocument(
        project=legacy_document.project,
        tablet_layouts=legacy_document.tablet_layouts,
        tablet_presets=legacy_document.tablet_presets,
        source_documents=legacy_document.source_documents,
        import_reports=legacy_document.import_reports,
        image_assets=legacy_document.image_assets,
        rock_code_profiles=profiles,
        rock_code_source_bindings=bindings,
    )


def load_project_document(path: str | Path, *, max_size_mb: int = 512) -> ProjectDocument:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.stat().st_size > max_size_mb * 1024 * 1024:
        raise ProjectFormatError(f"Файл проекта превышает лимит {max_size_mb} МБ")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectFormatError(f"Не удалось прочитать проект: {source}") from exc
    if not isinstance(raw, dict):
        raise ProjectFormatError("Корень проекта должен быть JSON-объектом")
    try:
        document = project_document_from_dict(raw)
        try:
            document.source_documents = _v28.load_source_documents(
                source, dict(raw.get("source_artifacts", {}))
            )
            _v28._validate_report_artifact_consistency(document)
        except _v28.SourceArtifactError as exc:
            raise ProjectFormatError(str(exc)) from exc
        try:
            document.image_assets = _v28.load_image_assets(source, raw.get("image_assets", {}))
            missing_logo_assets = sorted(
                {entry.asset_id for entry in document.project.logo_catalog.values()}
                - set(document.image_assets)
            )
            if missing_logo_assets:
                raise ProjectFormatError(
                    "Каталог логотипов ссылается на отсутствующие image assets: "
                    + ", ".join(missing_logo_assets)
                )
            missing_passport_assets = {
                asset_ref
                for well in document.project.wells.values()
                if well.passport is not None
                for asset_ref in well.passport.logo_refs.values()
                if asset_ref
            } - set(document.image_assets)
            if missing_passport_assets:
                raise ProjectFormatError(
                    "Паспорт скважины ссылается на отсутствующие image assets"
                )
        except _v28.ImageAssetError as exc:
            raise ProjectFormatError(str(exc)) from exc
        return document
    except ProjectFormatError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectFormatError("Файл содержит некорректные данные проекта") from exc


def load_project(path: str | Path, *, max_size_mb: int = 512) -> Project:
    return load_project_document(path, max_size_mb=max_size_mb).project


def __getattr__(name: str) -> Any:
    """Keep compatibility for public helpers that remain unchanged from v28."""

    return getattr(_v28, name)
