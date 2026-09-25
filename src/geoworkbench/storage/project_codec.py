"""Project codec v35 for well-level gas-context event persistence."""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any, cast

from geoworkbench.domain.localized_content import (
    normalize_content_language,
    validate_localized_texts,
)
from geoworkbench.domain.gas_context_events import (
    GasContextEvent,
    GasContextEventType,
    InterpretationImpact,
)
from geoworkbench.domain.models import DepthDomain, DescriptionTemplateBlock, Project
from geoworkbench.domain.translation_status import TranslationState, TranslationStatus
from geoworkbench.storage import project_codec_v29 as _v29
from geoworkbench.storage.project_codec_v29 import ProjectDocument, ProjectFormatError


PROJECT_FORMAT_VERSION = 35
_MAX_TEMPLATE_BLOCKS_PER_SAMPLE = 10_000
_BLOCK_KEYS = {"block_id", "template_id", "template_version", "text_i18n"}
_GAS_CONTEXT_EVENT_KEYS_V35_LEGACY = {
    "event_id",
    "event_type",
    "top_depth",
    "bottom_depth",
    "impact",
    "confirmed",
    "reported_total_gas",
    "reported_unit",
    "comment",
    "source",
}
_GAS_CONTEXT_EVENT_KEYS = {
    *_GAS_CONTEXT_EVENT_KEYS_V35_LEGACY,
    "depth_domain",
}
_MAX_GAS_CONTEXT_EVENTS_PER_WELL = 100_000


def _validated_i18n(value: object, *, maximum: int) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ProjectFormatError("Некорректное локализованное поле интерпретации")
    try:
        return validate_localized_texts(
            cast("Mapping[str, str]", value),
            maximum=maximum,
            allow_undetermined=True,
        )
    except (TypeError, ValueError) as exc:
        raise ProjectFormatError("Некорректное локализованное поле интерпретации") from exc


def _validated_revisions(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ProjectFormatError("authored_field_revisions должен быть объектом")
    revisions: dict[str, int] = {}
    for field_id, revision in value.items():
        if not isinstance(field_id, str) or not field_id.strip():
            raise ProjectFormatError("ID авторского поля не может быть пустым")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
            raise ProjectFormatError("Ревизия авторского поля должна быть неотрицательной")
        revisions[field_id] = revision
    return revisions


def _validated_source_languages(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ProjectFormatError("authored_field_source_languages должен быть объектом")
    source_languages: dict[str, str] = {}
    for field_id, language in value.items():
        if not isinstance(field_id, str) or not field_id.strip():
            raise ProjectFormatError("ID авторского поля не может быть пустым")
        normalized_field_id = field_id.strip()
        if normalized_field_id in source_languages:
            raise ProjectFormatError("ID языков оригинала авторских полей не должны повторяться")
        if not isinstance(language, str):
            raise ProjectFormatError("Язык оригинала авторского поля должен быть строкой")
        try:
            source_languages[normalized_field_id] = normalize_content_language(language)
        except ValueError as exc:
            raise ProjectFormatError("Некорректный язык оригинала авторского поля") from exc
    return source_languages


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


def _gas_context_events_from_dict(data: object) -> list[GasContextEvent]:
    if not isinstance(data, list) or len(data) > _MAX_GAS_CONTEXT_EVENTS_PER_WELL:
        raise ProjectFormatError("gas_context_events должен быть ограниченным списком")
    events: list[GasContextEvent] = []
    for raw in data:
        if (
            not isinstance(raw, dict)
            or set(raw)
            not in {
                frozenset(_GAS_CONTEXT_EVENT_KEYS_V35_LEGACY),
                frozenset(_GAS_CONTEXT_EVENT_KEYS),
            }
        ):
            raise ProjectFormatError("Некорректная запись gas context event")
        try:
            impact_raw = raw["impact"]
            depth_domain_raw = raw.get("depth_domain")
            event = GasContextEvent(
                event_id=raw["event_id"],
                event_type=GasContextEventType(raw["event_type"]),
                top_depth=raw["top_depth"],
                bottom_depth=raw["bottom_depth"],
                depth_domain=(
                    DepthDomain(depth_domain_raw)
                    if depth_domain_raw is not None
                    else None
                ),
                impact=(
                    InterpretationImpact(impact_raw)
                    if impact_raw is not None
                    else None
                ),
                confirmed=raw["confirmed"],
                reported_total_gas=raw["reported_total_gas"],
                reported_unit=raw["reported_unit"],
                comment=raw["comment"],
                source=raw["source"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectFormatError("Некорректная запись gas context event") from exc
        events.append(event)
    ids = [event.event_id for event in events]
    if len(ids) != len(set(ids)):
        raise ProjectFormatError("ID gas context events не должны повторяться")
    return events


def _legacy_payload_and_blocks(
    data: dict[str, Any], version: int
) -> tuple[
    dict[str, Any],
    dict[tuple[str, str], list[DescriptionTemplateBlock]],
    dict[tuple[str, str], tuple[dict[str, str], dict[str, str]]],
    dict[tuple[str, str, str], tuple[dict[str, str], dict[str, str]]],
    dict[str, dict[str, dict[str, TranslationStatus]]],
    dict[str, dict[str, int]],
    dict[str, dict[str, str]],
    dict[str, list[GasContextEvent]],
]:
    legacy = deepcopy(data)
    found: dict[tuple[str, str], list[DescriptionTemplateBlock]] = {}
    interpretation_texts: dict[tuple[str, str], tuple[dict[str, str], dict[str, str]]] = {}
    interval_texts: dict[tuple[str, str, str], tuple[dict[str, str], dict[str, str]]] = {}
    translation_statuses: dict[str, dict[str, dict[str, TranslationStatus]]] = {}
    authored_field_revisions: dict[str, dict[str, int]] = {}
    authored_field_source_languages: dict[str, dict[str, str]] = {}
    gas_context_events: dict[str, list[GasContextEvent]] = {}
    root = legacy.get("project", legacy)
    wells = root.get("wells", {}) if isinstance(root, dict) else {}
    if not isinstance(wells, dict):
        raise ProjectFormatError("Список скважин должен быть объектом")
    for well_id, well in wells.items():
        if not isinstance(well, dict):
            continue
        raw_gas_context_events = well.pop("gas_context_events", [])
        if version >= 35:
            gas_context_events[str(well_id)] = _gas_context_events_from_dict(
                raw_gas_context_events
            )
        raw_source_languages = well.pop("authored_field_source_languages", {})
        if version >= 34:
            authored_field_source_languages[str(well_id)] = _validated_source_languages(
                raw_source_languages
            )
        raw_field_revisions = well.pop("authored_field_revisions", {})
        if version >= 33:
            authored_field_revisions[str(well_id)] = _validated_revisions(raw_field_revisions)
        raw_statuses = well.pop("translation_statuses", {})
        if version >= 32:
            if not isinstance(raw_statuses, dict):
                raise ProjectFormatError("translation_statuses должен быть объектом")
            parsed_fields: dict[str, dict[str, TranslationStatus]] = {}
            for field_id, languages in raw_statuses.items():
                if (
                    not isinstance(field_id, str)
                    or not field_id.strip()
                    or not isinstance(languages, dict)
                ):
                    raise ProjectFormatError("Некорректное состояние переводимого поля")
                parsed_languages: dict[str, TranslationStatus] = {}
                for language, raw_status in languages.items():
                    if not isinstance(raw_status, dict):
                        raise ProjectFormatError("Некорректное состояние перевода")
                    try:
                        language_code = normalize_content_language(language)
                        parsed_languages[language_code] = TranslationStatus(
                            state=TranslationState(raw_status["state"]),
                            source_language=raw_status["source_language"],
                            source_revision=raw_status["source_revision"],
                            translation_revision=raw_status.get("translation_revision", 0),
                            dependency_revisions=dict(raw_status.get("dependency_revisions", {})),
                        )
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ProjectFormatError("Некорректное состояние перевода") from exc
                parsed_fields[field_id] = parsed_languages
            translation_statuses[str(well_id)] = parsed_fields
        cuttings = well.get("cuttings", [])
        if not isinstance(cuttings, list):
            continue
        for sample in cuttings:
            if not isinstance(sample, dict):
                continue
            raw = sample.pop("description_template_blocks", [])
            if version < 30:
                continue
            if not isinstance(raw, list) or len(raw) > _MAX_TEMPLATE_BLOCKS_PER_SAMPLE:
                raise ProjectFormatError("История шаблонов описания слишком велика")
            blocks = [_template_block_from_dict(item) for item in raw]
            ids = [item.block_id for item in blocks]
            if len(ids) != len(set(ids)):
                raise ProjectFormatError("ID блоков шаблонов описания не должны повторяться")
            found[(str(well_id), str(sample.get("sample_id", "")))] = blocks
        interpretations = well.get("interpretations", {})
        if isinstance(interpretations, dict):
            for interpretation_id, interpretation in interpretations.items():
                if not isinstance(interpretation, dict):
                    continue
                name_i18n = interpretation.pop("name_i18n", {})
                description_i18n = interpretation.pop("description_i18n", {})
                if version >= 31:
                    interpretation_texts[(str(well_id), str(interpretation_id))] = (
                        _validated_i18n(name_i18n, maximum=200),
                        _validated_i18n(description_i18n, maximum=4_000),
                    )
                intervals = interpretation.get("intervals", [])
                if not isinstance(intervals, list):
                    continue
                for interval in intervals:
                    if not isinstance(interval, dict):
                        continue
                    label_i18n = interval.pop("label_i18n", {})
                    comment_i18n = interval.pop("comment_i18n", {})
                    if version >= 31:
                        interval_texts[
                            (
                                str(well_id),
                                str(interpretation_id),
                                str(interval.get("interval_id", "")),
                            )
                        ] = (
                            _validated_i18n(label_i18n, maximum=300),
                            _validated_i18n(comment_i18n, maximum=4_000),
                        )
    if version >= 30 and "format_version" in legacy:
        legacy["format_version"] = _v29.PROJECT_FORMAT_VERSION
    return (
        legacy,
        found,
        interpretation_texts,
        interval_texts,
        translation_statuses,
        authored_field_revisions,
        authored_field_source_languages,
        gas_context_events,
    )


def _attach_blocks(
    project: Project,
    blocks: dict[tuple[str, str], list[DescriptionTemplateBlock]],
    interpretation_texts: dict[tuple[str, str], tuple[dict[str, str], dict[str, str]]],
    interval_texts: dict[tuple[str, str, str], tuple[dict[str, str], dict[str, str]]],
    translation_statuses: dict[str, dict[str, dict[str, TranslationStatus]]],
    authored_field_revisions: dict[str, dict[str, int]],
    authored_field_source_languages: dict[str, dict[str, str]],
    gas_context_events: dict[str, list[GasContextEvent]],
) -> None:
    for well_id, well in project.wells.items():
        well.translation_statuses = translation_statuses.get(well_id, {})
        well.authored_field_revisions = authored_field_revisions.get(well_id, {})
        well.authored_field_source_languages = authored_field_source_languages.get(well_id, {})
        well.gas_context_events = gas_context_events.get(well_id, [])
        for sample in well.cuttings:
            sample.description_template_blocks = blocks.get((well_id, sample.sample_id), [])
        for interpretation_id, interpretation in well.interpretations.items():
            interpretation.name_i18n, interpretation.description_i18n = interpretation_texts.get(
                (well_id, interpretation_id), ({}, {})
            )
            for interval in interpretation.intervals:
                interval.label_i18n, interval.comment_i18n = interval_texts.get(
                    (well_id, interpretation_id, interval.interval_id), ({}, {})
                )


def project_from_dict(data: dict[str, Any]) -> Project:
    # A bare project object has no document-level version marker and therefore
    # follows the current schema. Versioned documents are handled below.
    version = _format_version(data) if "format_version" in data else PROJECT_FORMAT_VERSION
    (
        legacy,
        blocks,
        interpretation_texts,
        interval_texts,
        statuses,
        revisions,
        source_languages,
        gas_context_events,
    ) = _legacy_payload_and_blocks(data, version)
    project = _v29.project_from_dict(legacy)
    _attach_blocks(
        project,
        blocks,
        interpretation_texts,
        interval_texts,
        statuses,
        revisions,
        source_languages,
        gas_context_events,
    )
    return project


def project_document_from_dict(data: dict[str, Any]) -> ProjectDocument:
    (
        legacy,
        blocks,
        interpretation_texts,
        interval_texts,
        statuses,
        revisions,
        source_languages,
        gas_context_events,
    ) = _legacy_payload_and_blocks(data, _format_version(data))
    document = _v29.project_document_from_dict(legacy)
    _attach_blocks(
        document.project,
        blocks,
        interpretation_texts,
        interval_texts,
        statuses,
        revisions,
        source_languages,
        gas_context_events,
    )
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
