"""Project codec v30 for versioned cuttings-description template blocks."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from geoworkbench.domain.localized_content import validate_localized_texts
from geoworkbench.domain.models import DescriptionTemplateBlock, Project
from geoworkbench.storage import project_codec_v29 as _v29
from geoworkbench.storage.project_codec_v29 import ProjectDocument, ProjectFormatError


PROJECT_FORMAT_VERSION = 30
_MAX_TEMPLATE_BLOCKS_PER_SAMPLE = 10_000
_BLOCK_KEYS = {"block_id", "template_id", "template_version", "text_i18n"}


def _format_version(data: dict[str, Any]) -> int:
    version = data.get("format_version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ProjectFormatError("Некорректная версия формата проекта")
    if version > PROJECT_FORMAT_VERSION:
        raise ProjectFormatError(
            f"Версия проекта {version} новее поддерживаемой {PROJECT_FORMAT_VERSION}"
        )
    return version


def _template_block_from_dict(data: object) -> DescriptionTemplateBlock:
    if not isinstance(data, dict) or set(data) != _BLOCK_KEYS:
        raise ProjectFormatError("Некорректный блок шаблона описания шлама")
    block_id, template_id, version = (
        data["block_id"],
        data["template_id"],
        data["template_version"],
    )
    if not isinstance(block_id, str) or not block_id.strip():
        raise ProjectFormatError("ID блока шаблона описания не может быть пустым")
    if not isinstance(template_id, str) or not template_id.strip():
        raise ProjectFormatError("ID шаблона описания не может быть пустым")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ProjectFormatError("Некорректная версия шаблона описания")
    texts = validate_localized_texts(data["text_i18n"], maximum=2_000_000)
    if set(texts) != {"ru", "kk", "en"}:
        raise ProjectFormatError("Блок шаблона должен содержать снимок RU/KK/EN")
    return DescriptionTemplateBlock(block_id, template_id, version, texts)


def _legacy_payload_and_blocks(
    data: dict[str, Any], version: int
) -> tuple[dict[str, Any], dict[tuple[str, str], list[DescriptionTemplateBlock]]]:
    legacy = deepcopy(data)
    found: dict[tuple[str, str], list[DescriptionTemplateBlock]] = {}
    root = legacy.get("project", legacy)
    wells = root.get("wells", {}) if isinstance(root, dict) else {}
    if not isinstance(wells, dict):
        raise ProjectFormatError("Список скважин должен быть объектом")
    for well_id, well in wells.items():
        if not isinstance(well, dict):
            continue
        cuttings = well.get("cuttings", [])
        if not isinstance(cuttings, list):
            continue
        for sample in cuttings:
            if not isinstance(sample, dict):
                continue
            raw = sample.pop("description_template_blocks", [])
            if version < PROJECT_FORMAT_VERSION:
                continue
            if not isinstance(raw, list) or len(raw) > _MAX_TEMPLATE_BLOCKS_PER_SAMPLE:
                raise ProjectFormatError("История шаблонов описания слишком велика")
            blocks = [_template_block_from_dict(item) for item in raw]
            ids = [item.block_id for item in blocks]
            if len(ids) != len(set(ids)):
                raise ProjectFormatError("ID блоков шаблонов описания не должны повторяться")
            found[(str(well_id), str(sample.get("sample_id", "")))] = blocks
    if version == PROJECT_FORMAT_VERSION and "format_version" in legacy:
        legacy["format_version"] = _v29.PROJECT_FORMAT_VERSION
    return legacy, found


def _attach_blocks(
    project: Project,
    blocks: dict[tuple[str, str], list[DescriptionTemplateBlock]],
) -> None:
    for well_id, well in project.wells.items():
        for sample in well.cuttings:
            sample.description_template_blocks = blocks.get((well_id, sample.sample_id), [])


def project_from_dict(data: dict[str, Any]) -> Project:
    # A bare project object has no document-level version marker and therefore
    # follows the current schema. Versioned documents are handled below.
    version = _format_version(data) if "format_version" in data else PROJECT_FORMAT_VERSION
    legacy, blocks = _legacy_payload_and_blocks(data, version)
    project = _v29.project_from_dict(legacy)
    _attach_blocks(project, blocks)
    return project


def project_document_from_dict(data: dict[str, Any]) -> ProjectDocument:
    legacy, blocks = _legacy_payload_and_blocks(data, _format_version(data))
    document = _v29.project_document_from_dict(legacy)
    _attach_blocks(document.project, blocks)
    return document


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
    document = project_document_from_dict(raw)
    try:
        document.source_documents = _v29.load_source_documents(
            source, dict(raw.get("source_artifacts", {}))
        )
        _v29._validate_report_artifact_consistency(document)
        document.image_assets = _v29.load_image_assets(source, raw.get("image_assets", {}))
    except (_v29.SourceArtifactError, _v29.ImageAssetError) as exc:
        raise ProjectFormatError(str(exc)) from exc
    missing_logo_assets = {
        entry.asset_id for entry in document.project.logo_catalog.values()
    } - set(document.image_assets)
    if missing_logo_assets:
        raise ProjectFormatError(
            "Каталог логотипов ссылается на отсутствующие image assets: "
            + ", ".join(sorted(missing_logo_assets))
        )
    missing_passport_assets = {
        asset_ref
        for well in document.project.wells.values()
        if well.passport is not None
        for asset_ref in well.passport.logo_refs.values()
        if asset_ref
    } - set(document.image_assets)
    if missing_passport_assets:
        raise ProjectFormatError("Паспорт скважины ссылается на отсутствующие image assets")
    return document


def load_project(path: str | Path, *, max_size_mb: int = 512) -> Project:
    return load_project_document(path, max_size_mb=max_size_mb).project


def __getattr__(name: str) -> Any:
    return getattr(_v29, name)
