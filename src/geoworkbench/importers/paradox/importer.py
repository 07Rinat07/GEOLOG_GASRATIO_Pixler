from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable
import json
import math
import re

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    new_id,
)

from .analysis import analyze_table, convert_time_values
from .channel_dictionary import GeoScapeChannelDictionary
from .models import (
    ChannelMapping,
    DatasetClassification,
    DuplicateDepthPolicy,
    ParadoxImportPlan,
    ParadoxImportResult,
    ParadoxTable,
    QualitySummary,
)
from .profiles import schema_signature
from .reader import read_paradox


class ParadoxImportError(RuntimeError):
    pass


# GeoScape server installations normally register depth on a 0.2 m grid.
# A particular source table can still contain a different actual interval
# (the supplied BLData sample is effectively 0.4 m).  Keep both facts separate:
# LAS STEP describes rows that really exist, while this constant is stored as
# source-system metadata and shown by the import dialog.
GEOSCAPE_STANDARD_DEPTH_STEP_M = 0.2


def default_mappings(
    table: ParadoxTable,
    *,
    language: str = "ru",
    dictionary: GeoScapeChannelDictionary | None = None,
) -> tuple[ChannelMapping, ...]:
    catalog = dictionary or GeoScapeChannelDictionary.load()
    mappings: list[ChannelMapping] = []
    for field in table.fields:
        definition = catalog.resolve(field.name)
        mappings.append(
            ChannelMapping(
                source_name=field.name,
                mnemonic=(definition.mnemonic if definition else _safe_mnemonic(field.name)),
                unit=(definition.unit if definition else ""),
                description=(
                    definition.localized_name(language)
                    if definition
                    else _source_channel_description(language, field.name)
                ),
                import_enabled=field.is_numeric,
            )
        )
    return tuple(mappings)


def import_paradox(
    path: str | Path,
    plan: ParadoxImportPlan | None = None,
    *,
    table: ParadoxTable | None = None,
    kind: DatasetKind = DatasetKind.USER,
    quality: QualitySummary | None = None,
    progress: Callable[[str, int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> ParadoxImportResult:
    parsed = table or read_paradox(path, progress=progress, cancelled=cancelled)
    _check_cancelled(cancelled)
    if quality is None:
        _notify(progress, "analysis", 0, 1)
        quality = analyze_table(parsed)
        _notify(progress, "analysis", 1, 1)
    selected = plan or _automatic_plan(parsed, quality)
    classification = DatasetClassification(selected.classification)
    duplicate_policy = DuplicateDepthPolicy(selected.duplicate_depth_policy)
    mappings = selected.mappings or default_mappings(parsed, language=selected.language)
    by_source = {mapping.source_name: mapping for mapping in mappings}

    depth_field = selected.depth_field
    time_field = selected.time_field
    if depth_field is not None and depth_field not in parsed.columns:
        raise ParadoxImportError(f"Канал глубины не найден: {depth_field}")
    if time_field is not None and time_field not in parsed.columns:
        raise ParadoxImportError(f"Канал времени не найден: {time_field}")
    if depth_field is None and time_field is None:
        raise ParadoxImportError("Нужно явно выбрать канал глубины или времени")

    use_time = selected.active_role == "time" or (
        selected.active_role == "auto" and depth_field is None and time_field is not None
    )
    depth_values = (
        np.asarray(parsed.columns[depth_field].values, dtype=np.float64)
        if depth_field is not None
        else None
    )
    elapsed: np.ndarray | None = None
    datetimes: np.ndarray | None = None
    time_representation = ""
    if time_field is not None:
        elapsed, datetimes, time_representation = convert_time_values(
            np.asarray(parsed.columns[time_field].values, dtype=np.float64)
        )

    if use_time:
        if elapsed is None:
            raise ParadoxImportError("Выбран временной режим без канала времени")
        primary_values = elapsed
        depth_domain = DepthDomain.TIME
        primary_role = IndexRole.TIME
        primary_type = IndexType.RELATIVE_TIME
        primary_mnemonic = "TIME"
        primary_unit = "s"
    else:
        if depth_values is None:
            raise ParadoxImportError("Выбран глубинный режим без канала глубины")
        primary_values = depth_values
        depth_domain = DepthDomain.MD
        primary_role = IndexRole.DEPTH
        primary_type = IndexType.MD
        primary_mnemonic = "DEPT"
        primary_unit = "m"

    order = np.arange(parsed.rows_read)
    if selected.sort_by_index:
        sort_key = np.where(np.isfinite(primary_values), primary_values, np.inf)
        order = np.argsort(sort_key, kind="stable")
        primary_values = primary_values[order]
        if depth_values is not None:
            depth_values = depth_values[order]
        if elapsed is not None:
            elapsed = elapsed[order]
        if datetimes is not None:
            datetimes = datetimes[order]

    dataset_id = new_id()
    primary_index_id = f"{dataset_id}:paradox-primary"
    indexes: dict[str, DatasetIndex] = {
        primary_index_id: DatasetIndex(
            primary_index_id,
            primary_mnemonic,
            primary_type,
            primary_role,
            primary_unit,
            primary_values,
            confidence=1.0,
            evidence=("confirmed in GeoScape/Paradox import dialog",),
        )
    }
    if depth_values is not None and use_time:
        depth_index_id = f"{dataset_id}:paradox-depth"
        confidence = _candidate_confidence(quality.depth_candidates, depth_field)
        indexes[depth_index_id] = DatasetIndex(
            depth_index_id,
            "DEPTH", IndexType.MD, IndexRole.DEPTH, "m", depth_values,
            confidence=confidence,
            evidence=(f"source field {depth_field}",),
        )
    if elapsed is not None and not use_time:
        elapsed_id = f"{dataset_id}:paradox-elapsed"
        indexes[elapsed_id] = DatasetIndex(
            elapsed_id,
            "TIME", IndexType.RELATIVE_TIME, IndexRole.TIME, "s", elapsed,
            confidence=_candidate_confidence(quality.time_candidates, time_field),
            evidence=(f"source field {time_field}; {time_representation}",),
        )
    if datetimes is not None:
        datetime_id = f"{dataset_id}:paradox-datetime"
        indexes[datetime_id] = DatasetIndex(
            datetime_id,
            "DATETIME", IndexType.DATETIME, IndexRole.TIME, None, datetimes,
            confidence=_candidate_confidence(quality.time_candidates, time_field),
            evidence=(f"source field {time_field}; {time_representation}",),
            datetime_format=time_representation,
        )

    headers = {
        "WELL": parsed.source.stem,
        "NULL": f"{selected.null_value:g}",
        "STRT": _finite_text(primary_values, first=True),
        "STOP": _finite_text(primary_values, first=False),
        "STEP": _nominal_step_text(primary_values),
    }
    if datetimes is not None:
        valid_datetimes = datetimes[~np.isnat(datetimes)]
        if valid_datetimes.size:
            start_text = np.datetime_as_string(valid_datetimes[0], unit="s")
            date_text, time_text = start_text.split("T", 1)
            headers["DATE"] = date_text
            headers["TIME"] = time_text

    actual_depth_step = (
        _nominal_step_value(depth_values) if depth_values is not None else 0.0
    )
    dataset = Dataset(
        dataset_id=dataset_id,
        name=parsed.source.stem,
        kind=kind,
        depth_domain=depth_domain,
        depth=np.asarray(primary_values, dtype=np.float64),
        source_path=parsed.source,
        headers=headers,
        parameters={
            "SOURCE_FORMAT": "GeoScape/Paradox DB",
            "SOURCE_FILE": str(parsed.source),
            "SOURCE_BUNDLE": "; ".join(str(item) for item in parsed.bundle.files),
            "IMPORT_DATE_UTC": datetime.now(timezone.utc).isoformat(),
            "IMPORTER_VERSION": "1.0",
            "IMPORT_PROFILE": selected.profile_name or "",
            "PARADOX_VERSION": parsed.header.version_label,
            "PARADOX_RECORDS": str(parsed.rows_read),
            "PARADOX_FIELDS": str(len(parsed.fields)),
            "PARADOX_CLASSIFICATION": classification.value,
            "PARADOX_DEPTH_FIELD": depth_field or "",
            "PARADOX_TIME_FIELD": time_field or "",
            "PARADOX_TIME_REPRESENTATION": time_representation,
            "GEOSCAPE_STANDARD_DEPTH_STEP_M": f"{GEOSCAPE_STANDARD_DEPTH_STEP_M:g}",
            "PARADOX_ACTUAL_DEPTH_STEP_M": (
                f"{actual_depth_step:g}" if actual_depth_step > 0 else ""
            ),
            "PARADOX_DEPTH_STEP_MATCHES_STANDARD": (
                ""
                if actual_depth_step <= 0
                else "true"
                if np.isclose(
                    actual_depth_step,
                    GEOSCAPE_STANDARD_DEPTH_STEP_M,
                    rtol=0.0,
                    atol=1e-6,
                )
                else "false"
            ),
            "PARADOX_WARNINGS": json.dumps(
                [issue.message for issue in quality.issues], ensure_ascii=False
            ),
            "SOURCE_READ_ONLY": "true",
        },
        indexes=indexes,
        active_index_id=primary_index_id,
        version_headers={"VERS": "2.0", "WRAP": "NO"},
    )

    used_mnemonics = {primary_mnemonic.casefold()}
    curves: dict[str, CurveData] = {}
    represented_sources = {
        name for name in (depth_field, time_field) if name is not None
    }
    raw_time_curve_mnemonic = ""
    _notify(progress, "create", 0, len(parsed.fields))
    for field_position, field in enumerate(parsed.fields, start=1):
        _check_cancelled(cancelled)
        _notify(progress, "create", field_position, len(parsed.fields))
        mapping = by_source.get(field.name)
        if mapping is None or not mapping.import_enabled or not field.is_numeric:
            continue
        if selected.drop_empty_channels and parsed.columns[field.name].is_empty:
            continue

        source_values = np.asarray(parsed.columns[field.name].values, dtype=np.float64)[order]
        if field.name == time_field:
            raw_mnemonic = _unique_mnemonic(
                f"{mapping.mnemonic or _safe_mnemonic(field.name)}_RAW",
                used_mnemonics,
            )
            used_mnemonics.add(raw_mnemonic.casefold())
            raw_curve_id = new_id()
            curves[raw_curve_id] = CurveData(
                CurveMetadata(
                    raw_curve_id,
                    raw_mnemonic,
                    raw_mnemonic,
                    _raw_time_unit(time_representation, mapping.unit),
                    (
                        _raw_time_description(
                            selected.language, field.name, time_representation
                        )
                    ),
                    dataset_id,
                    provenance=f"paradox:{field.name}:{field.type_name}:raw-time",
                ),
                source_values,
            )
            raw_time_curve_mnemonic = raw_mnemonic
            represented_sources.add(field.name)

        primary_source = time_field if use_time else depth_field
        if field.name == primary_source:
            continue

        values = source_values
        if use_time and field.name == depth_field and depth_values is not None:
            values = depth_values
        elif not use_time and field.name == time_field and elapsed is not None:
            values = elapsed
        requested_mnemonic = mapping.mnemonic
        unit = mapping.unit
        description = mapping.description
        if (
            use_time
            and field.name == depth_field
            and requested_mnemonic == _safe_mnemonic(field.name)
        ):
            requested_mnemonic, unit, description = (
                "DEPTH",
                unit or "m",
                description or "MEASURED DEPTH",
            )
        elif (
            not use_time
            and field.name == time_field
            and requested_mnemonic == _safe_mnemonic(field.name)
        ):
            requested_mnemonic, unit, description = (
                "TIME",
                unit or "s",
                description or "ELAPSED TIME",
            )
        mnemonic = _unique_mnemonic(requested_mnemonic, used_mnemonics)
        used_mnemonics.add(mnemonic.casefold())
        curve_id = new_id()
        curves[curve_id] = CurveData(
            CurveMetadata(
                curve_id,
                mnemonic,
                mnemonic,
                unit or None,
                description or _source_channel_description(selected.language, field.name),
                dataset_id,
                provenance=f"paradox:{field.name}:{field.type_name}",
            ),
            values,
        )
        represented_sources.add(field.name)

    _check_cancelled(cancelled)
    dataset.curves = curves
    if raw_time_curve_mnemonic:
        dataset.parameters["PARADOX_TIME_RAW_CURVE"] = raw_time_curve_mnemonic
    skipped_records = _apply_duplicate_depth_policy(dataset, duplicate_policy)
    dataset.parameters["PARADOX_DUPLICATE_DEPTH_POLICY"] = duplicate_policy.value
    dataset.parameters["PARADOX_DUPLICATE_ROWS_REMOVED"] = str(skipped_records)
    dataset.parameters["PARADOX_DROP_EMPTY_CHANNELS"] = str(selected.drop_empty_channels).lower()
    represented_sources = {
        field_name
        for field_name in represented_sources
        if not (
            selected.drop_empty_channels
            and parsed.columns[field_name].is_empty
            and field_name not in {depth_field, time_field}
        )
    }
    imported = len(represented_sources)
    skipped = len(parsed.fields) - imported
    severity_counts: dict[str, int] = {}
    for issue in quality.issues:
        key = issue.severity.value
        severity_counts[key] = severity_counts.get(key, 0) + 1
    empty_channels = sum(column.is_empty for column in parsed.columns.values())
    dataset.parameters.update(
        {
            "PARADOX_ACTIVE_ROLE": selected.active_role,
            "PARADOX_NULL_VALUE": f"{selected.null_value:g}",
            "PARADOX_SORT_BY_INDEX": str(selected.sort_by_index).lower(),
            "PARADOX_IMPORTED_CHANNELS": str(imported),
            "PARADOX_SKIPPED_CHANNELS": str(skipped),
            "PARADOX_SKIPPED_RECORDS": str(skipped_records),
            "PARADOX_EMPTY_CHANNELS": str(empty_channels),
            "PARADOX_ISSUE_COUNTS": json.dumps(severity_counts, sort_keys=True),
            "PARADOX_SCHEMA_SIGNATURE": schema_signature(parsed),
            "PARADOX_APPLIED_CORRECTIONS": json.dumps(
                {
                    "duplicate_depth_policy": duplicate_policy.value,
                    "duplicate_rows_removed": skipped_records,
                    "sorted_by_index": selected.sort_by_index,
                    "dropped_empty_channels": selected.drop_empty_channels,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        }
    )
    return ParadoxImportResult(dataset, parsed, quality, imported, skipped, skipped_records)


def _notify(
    callback: Callable[[str, int, int], None] | None,
    phase: str,
    current: int,
    total: int,
) -> None:
    if callback is not None:
        callback(phase, current, total)


def _check_cancelled(callback: Callable[[], bool] | None) -> None:
    if callback is not None and callback():
        raise ParadoxImportError("Импорт Paradox отменён пользователем")


def _automatic_plan(table: ParadoxTable, quality) -> ParadoxImportPlan:
    depth = quality.depth_candidates[0].field_name if quality.depth_candidates else None
    time = quality.time_candidates[0].field_name if quality.time_candidates else None
    classification = quality.classification
    if classification is DatasetClassification.UNDEFINED:
        depth = None
        time = None
    return ParadoxImportPlan(
        classification=classification,
        depth_field=depth,
        time_field=time,
        active_role="depth" if depth is not None else "time",
        mappings=default_mappings(table),
    )


def _candidate_confidence(candidates, field_name: str | None) -> float:
    if field_name is None:
        return 0.0
    return next((item.confidence for item in candidates if item.field_name == field_name), 0.5)


def _safe_mnemonic(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_")
    return (normalized or "CURVE")[:32]


def _unique_mnemonic(value: str, used: set[str]) -> str:
    base = _safe_mnemonic(value)
    if base.casefold() not in used:
        return base
    suffix = 2
    while f"{base}_{suffix}".casefold() in used:
        suffix += 1
    return f"{base}_{suffix}"


def _apply_duplicate_depth_policy(
    dataset: Dataset,
    policy: DuplicateDepthPolicy,
) -> int:
    if policy is DuplicateDepthPolicy.KEEP_ALL or dataset.active_index.role is not IndexRole.DEPTH:
        return 0
    depth = np.asarray(dataset.active_index.values, dtype=np.float64)
    groups = _equal_depth_groups(depth)
    removed = int(sum(max(0, len(rows) - 1) for rows in groups))
    if removed == 0:
        return 0

    if policy in {DuplicateDepthPolicy.FIRST, DuplicateDepthPolicy.LAST}:
        selected_rows = np.asarray(
            [rows[0] if policy is DuplicateDepthPolicy.FIRST else rows[-1] for rows in groups],
            dtype=np.int64,
        )
        for index in dataset.indexes.values():
            index.values = np.asarray(index.values)[selected_rows].copy()
        for curve in dataset.curves.values():
            curve.values = np.asarray(curve.values, dtype=np.float64)[selected_rows].copy()
    else:
        reducer = np.nanmean if policy is DuplicateDepthPolicy.MEAN else np.nanmedian
        for index in dataset.indexes.values():
            index.values = _aggregate_index_values(index, groups, reducer)
        for curve in dataset.curves.values():
            values = np.asarray(curve.values, dtype=np.float64)
            curve.values = np.asarray(
                [
                    _reduce_numeric(values[np.asarray(rows, dtype=np.int64)], reducer)
                    for rows in groups
                ],
                dtype=np.float64,
            )

    active = dataset.active_index
    dataset.depth = np.asarray(active.values, dtype=np.float64)
    finite = dataset.depth[np.isfinite(dataset.depth)]
    if finite.size:
        dataset.headers["STRT"] = f"{float(finite[0]):g}"
        dataset.headers["STOP"] = f"{float(finite[-1]):g}"
        dataset.headers["STEP"] = _nominal_step_text(dataset.depth)
    return removed


def _equal_depth_groups(depth: np.ndarray) -> list[list[int]]:
    groups: list[list[int]] = []
    positions: dict[float, int] = {}
    for row, raw in enumerate(depth):
        value = float(raw)
        if not math.isfinite(value):
            groups.append([row])
            continue
        position = positions.get(value)
        if position is None:
            positions[value] = len(groups)
            groups.append([row])
        else:
            groups[position].append(row)
    return groups


def _aggregate_index_values(index: DatasetIndex, groups: list[list[int]], reducer) -> np.ndarray:
    values = np.asarray(index.values)
    if index.index_type is IndexType.DATETIME:
        nanos = values.astype("datetime64[ns]").astype(np.int64)
        nat = np.iinfo(np.int64).min
        aggregated = np.full(len(groups), nat, dtype=np.int64)
        for position, rows in enumerate(groups):
            selected = nanos[np.asarray(rows, dtype=np.int64)]
            valid = selected[selected != nat]
            if valid.size:
                base = int(valid[0])
                aggregated[position] = base + int(reducer(valid - base))
        return aggregated.astype("datetime64[ns]")
    numeric = np.asarray(values, dtype=np.float64)
    return np.asarray(
        [_reduce_numeric(numeric[np.asarray(rows, dtype=np.int64)], reducer) for rows in groups],
        dtype=np.float64,
    )


def _reduce_numeric(values: np.ndarray, reducer) -> float:
    finite = values[np.isfinite(values)]
    if not finite.size:
        return math.nan
    return float(reducer(finite))


def _source_channel_description(language: str, field_name: str) -> str:
    templates = {
        "ru": "Исходный канал {field}",
        "kk": "Бастапқы арна {field}",
        "en": "Source channel {field}",
    }
    return templates.get(language, templates["ru"]).format(field=field_name)


def _raw_time_description(language: str, field_name: str, representation: str) -> str:
    templates = {
        "ru": "Исходное числовое значение времени {field} ({representation})",
        "kk": "Уақыттың бастапқы сандық мәні {field} ({representation})",
        "en": "Original numeric time value {field} ({representation})",
    }
    return templates.get(language, templates["ru"]).format(
        field=field_name, representation=representation
    )


def _raw_time_unit(representation: str, configured_unit: str) -> str | None:
    if configured_unit:
        return configured_unit
    if representation == "ole-automation-days":
        return "d"
    if representation.startswith("unix-"):
        return representation.removeprefix("unix-")
    if representation == "relative-milliseconds":
        return "ms"
    return "s"


def _finite_text(values: np.ndarray, *, first: bool) -> str:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if not finite.size:
        return ""
    return f"{float(finite[0] if first else finite[-1]):g}"


def _nominal_step_text(values: np.ndarray) -> str:
    value = _nominal_step_value(values)
    return f"{value:g}" if value > 0 else "0"


def _nominal_step_value(values: np.ndarray) -> float:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    positive = np.diff(finite)
    positive = positive[positive > 0]
    if not positive.size:
        return 0.0
    return float(np.median(positive))


class ParadoxImportPlugin:
    """Adapter for the application's shared importer protocol."""

    from geoworkbench.plugins.api import PluginMetadata

    metadata = PluginMetadata(
        plugin_id="geoworkbench.import.paradox",
        name="GeoScape / Borland Paradox DB",
        plugin_version="1.0",
        description="Read-only Paradox DB importer using the common Dataset model",
    )

    def supported_extensions(self) -> tuple[str, ...]:
        return (".db",)

    def probe(self, path: Path) -> float:
        from .detector import probe_db_format

        result = probe_db_format(path)
        return result.confidence if result.is_paradox else 0.0

    def import_data(self, path: Path) -> Dataset:
        table = read_paradox(path)
        quality = analyze_table(table)
        if quality.classification in {DatasetClassification.MIXED, DatasetClassification.UNDEFINED}:
            raise ParadoxImportError(
                "Структура требует ручного выбора глубины/времени; используйте окно импорта"
            )
        return import_paradox(path, table=table).dataset
