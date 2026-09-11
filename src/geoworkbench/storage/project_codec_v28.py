"""Frozen project codec v28 compatibility layer for WELL-02 late-analysis audit.

Version 28 adds one well-level analysis ledger over the frozen v27 decoder.
Newer project codecs delegate legacy reconstruction to this module.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from geoworkbench.domain.analysis_update import (
    AnalysisCellChange,
    AnalysisField,
    AnalysisUpdateRecord,
)
from geoworkbench.domain.models import Project
from geoworkbench.storage import project_codec_v27 as _v27
from geoworkbench.storage.project_codec_v27 import ProjectDocument, ProjectFormatError
from geoworkbench.storage.project_migrations import (
    ProjectMigrationError,
    migrate_project_payload,
)


PROJECT_FORMAT_VERSION = 28
_MAX_ANALYSIS_HISTORY_RECORDS = 10_000
_MAX_ANALYSIS_CHANGES = 10_000


def _require_exact_keys(data: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ProjectFormatError(f"{label} содержит неизвестные поля: {names}")


def _analysis_cell_change_from_dict(data: object) -> AnalysisCellChange:
    if not isinstance(data, dict):
        raise ProjectFormatError("Изменение отдельного анализа должно быть объектом")
    _require_exact_keys(
        data,
        {"sample_id", "top_depth", "bottom_depth", "field", "old_value", "new_value"},
        "analysis cell change",
    )
    field = data.get("field")
    if not isinstance(field, str):
        raise ProjectFormatError("Поле изменения анализа должно быть строкой")
    try:
        return AnalysisCellChange(**{**data, "field": AnalysisField(field)})
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectFormatError("Некорректное изменение отдельного анализа") from exc


def _analysis_update_record_from_dict(data: object) -> AnalysisUpdateRecord:
    if not isinstance(data, dict):
        raise ProjectFormatError("Запись истории отдельного анализа должна быть объектом")
    _require_exact_keys(
        data,
        {
            "update_id",
            "well_id",
            "source_name",
            "source_sha256",
            "imported_at",
            "selected_fields",
            "changes",
            "well_sha256_before",
            "well_sha256_after",
        },
        "analysis update record",
    )
    raw_fields = data.get("selected_fields")
    raw_changes = data.get("changes")
    if (
        not isinstance(raw_fields, list)
        or not raw_fields
        or len(raw_fields) > len(AnalysisField)
        or not all(isinstance(item, str) for item in raw_fields)
    ):
        raise ProjectFormatError("Некорректный selected_fields истории анализа")
    if (
        not isinstance(raw_changes, list)
        or not raw_changes
        or len(raw_changes) > _MAX_ANALYSIS_CHANGES
    ):
        raise ProjectFormatError("Некорректный changes истории анализа")
    try:
        return AnalysisUpdateRecord(
            **{
                **data,
                "selected_fields": tuple(AnalysisField(item) for item in raw_fields),
                "changes": tuple(_analysis_cell_change_from_dict(item) for item in raw_changes),
            }
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectFormatError("Некорректная история отдельных анализов") from exc


def _analysis_history_from_dict(data: object) -> list[AnalysisUpdateRecord]:
    if not isinstance(data, list) or len(data) > _MAX_ANALYSIS_HISTORY_RECORDS:
        raise ProjectFormatError("История отдельных анализов должна быть списком")
    return [_analysis_update_record_from_dict(item) for item in data]


def _analysis_histories(project_data: dict[str, Any]) -> dict[str, list[AnalysisUpdateRecord]]:
    wells = project_data.get("wells")
    if not isinstance(wells, dict):
        return {}
    histories: dict[str, list[AnalysisUpdateRecord]] = {}
    for well_key, raw_well in wells.items():
        if not isinstance(well_key, str) or not isinstance(raw_well, dict):
            continue
        histories[well_key] = _analysis_history_from_dict(
            raw_well.get("analysis_update_history", [])
        )
    return histories


def _without_analysis_histories(project_data: dict[str, Any]) -> dict[str, Any]:
    stripped = dict(project_data)
    wells = project_data.get("wells")
    if not isinstance(wells, dict):
        return stripped
    stripped_wells: dict[object, object] = {}
    for well_key, raw_well in wells.items():
        if isinstance(raw_well, dict):
            well_copy = dict(raw_well)
            well_copy.pop("analysis_update_history", None)
            stripped_wells[well_key] = well_copy
        else:
            stripped_wells[well_key] = raw_well
    stripped["wells"] = stripped_wells
    return stripped


def _attach_analysis_histories(
    project: Project,
    histories: dict[str, list[AnalysisUpdateRecord]],
) -> None:
    for well_key, records in histories.items():
        well = project.wells.get(well_key)
        if well is None:
            raise ProjectFormatError(
                f"История отдельных анализов ссылается на неизвестную скважину: {well_key}"
            )
        if any(record.well_id != well.well_id for record in records):
            raise ProjectFormatError(
                f"История отдельных анализов не соответствует скважине: {well_key}"
            )
        well.analysis_update_history = records


def project_from_dict(data: dict[str, Any]) -> Project:
    histories = _analysis_histories(data)
    project = _v27.project_from_dict(_without_analysis_histories(data))
    _attach_analysis_histories(project, histories)
    return project


def project_document_from_dict(data: dict[str, Any]) -> ProjectDocument:
    """Migrate to v28 and decode the new ledger without changing v27 semantics."""
    try:
        migrated = migrate_project_payload(data, PROJECT_FORMAT_VERSION)
    except ProjectMigrationError as exc:
        raise ProjectFormatError(str(exc)) from exc
    raw_project = migrated.get("project")
    if not isinstance(raw_project, dict):
        raise ProjectFormatError("Поле 'project' отсутствует или имеет неверный тип")
    histories = _analysis_histories(raw_project)
    legacy_payload = dict(migrated)
    legacy_payload["format_version"] = 27
    legacy_payload["project"] = _without_analysis_histories(raw_project)
    document = _v27.project_document_from_dict(legacy_payload)
    _attach_analysis_histories(document.project, histories)
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
    try:
        document = project_document_from_dict(raw)
        try:
            document.source_documents = _v27.load_source_documents(
                source, dict(raw.get("source_artifacts", {}))
            )
            _v27._validate_report_artifact_consistency(document)
        except _v27.SourceArtifactError as exc:
            raise ProjectFormatError(str(exc)) from exc
        try:
            document.image_assets = _v27.load_image_assets(source, raw.get("image_assets", {}))
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
        except _v27.ImageAssetError as exc:
            raise ProjectFormatError(str(exc)) from exc
        return document
    except ProjectFormatError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectFormatError("Файл содержит некорректные данные проекта") from exc


def load_project(path: str | Path, *, max_size_mb: int = 512) -> Project:
    return load_project_document(path, max_size_mb=max_size_mb).project


def __getattr__(name: str) -> Any:
    """Keep compatibility for public helpers that remain unchanged from v27."""
    return getattr(_v27, name)
