from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from importlib import import_module
import json
from pathlib import Path, PurePosixPath
import platform
import re
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

from geoworkbench.catalogs.sensors import SensorCatalog, active_sensor_catalog
from geoworkbench.importers.paradox.channel_dictionary import (
    ChannelDefinition,
    GeoScapeChannelDictionary,
)

from .container import extract_gs2_metadata

if TYPE_CHECKING:
    from geoworkbench.domain.models import Dataset


_TECHNICAL_CHANNEL = re.compile(
    r"^(?:SB?\d+|P\d+|TIME|DATE|DATETIME|DEPTH)$",
    re.IGNORECASE,
)
_GS2_TABLE_ID = re.compile(r"^GS2#(?P<identifier>\d+)", re.IGNORECASE)
_METADATA_TABLE_NAMES = {
    "FORMULAS",
    "LOGGINGSERVICE",
    "PROJECT",
    "PROJECTS",
    "WELL",
    "WELLINFO",
    "WELLINFORMATION",
    "WELLS",
}
_METADATA_TABLE_TOKENS = ("CHANNEL", "CURVE", "PARAMETER", "SENSOR", "SIGNAL")


class Gs2MetadataState(StrEnum):
    LOADED = "loaded"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Gs2MetadataDiagnostic:
    code: str
    message: str
    action: str = ""
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Gs2ChannelMetadata:
    source_name: str
    mnemonic: str
    unit: str = ""
    description: str = ""
    parameter_id: str = ""
    source_member: str = ""
    subset: str = ""
    origin_table: str = ""


@dataclass(frozen=True, slots=True)
class Gs2FormulaMetadata:
    name: str
    expression: str = ""
    description: str = ""
    parameter_id: str = ""
    subset: str = ""


@dataclass(frozen=True, slots=True)
class Gs2WellMetadata:
    identifier: str = ""
    uid: str = ""
    name: str = ""
    country: str = ""
    field: str = ""
    area: str = ""
    company: str = ""
    station_model: str = ""
    origin_table: str = ""


@dataclass(frozen=True, slots=True)
class Gs2Metadata:
    source: Path
    database_member: str
    state: Gs2MetadataState
    adapter: str = ""
    database_tables: tuple[str, ...] = ()
    channels: tuple[Gs2ChannelMetadata, ...] = ()
    formulas: tuple[Gs2FormulaMetadata, ...] = ()
    wells: tuple[Gs2WellMetadata, ...] = ()
    diagnostics: tuple[Gs2MetadataDiagnostic, ...] = ()

    @property
    def primary_well(self) -> Gs2WellMetadata | None:
        return self.wells[0] if self.wells else None


@dataclass(frozen=True, slots=True)
class AccessTable:
    name: str
    rows: tuple[Mapping[str, object], ...]


@dataclass(frozen=True, slots=True)
class AccessSnapshot:
    adapter: str
    table_names: tuple[str, ...]
    tables: tuple[AccessTable, ...]
    diagnostics: tuple[Gs2MetadataDiagnostic, ...] = ()


class AccessMetadataBackend(Protocol):
    def read(self, source: Path) -> AccessSnapshot: ...


class Gs2MetadataBackendUnavailable(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        action: str = "",
        details: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.action = action
        self.details = details


class QtOdbcAccessBackend:
    """Read selected Jet/Access tables through the Qt ODBC plugin.

    PySide6 is already an application dependency, so this adapter does not
    impose another Python package. The operating system still needs a
    Microsoft Access ODBC driver with the same bitness as the application.
    """

    adapter_name = "Qt ODBC / Microsoft Access"
    driver_names = (
        "Microsoft Access Driver (*.mdb, *.accdb)",
        "Microsoft Access Driver (*.mdb)",
    )

    def __init__(self, *, row_limit: int = 50_000) -> None:
        self.row_limit = max(1, int(row_limit))

    def read(self, source: Path) -> AccessSnapshot:
        try:
            qt_sql = import_module("PySide6.QtSql")
        except (ImportError, ModuleNotFoundError) as exc:
            raise Gs2MetadataBackendUnavailable(
                "qt-sql-unavailable",
                "Модуль PySide6.QtSql недоступен",
                action="Установите полную сборку PySide6 с плагином QODBC.",
                details=(str(exc),),
            ) from exc

        database_class = qt_sql.QSqlDatabase
        if not database_class.isDriverAvailable("QODBC"):
            available = tuple(str(item) for item in database_class.drivers())
            raise Gs2MetadataBackendUnavailable(
                "qt-odbc-unavailable",
                "В сборке Qt отсутствует драйвер QODBC",
                action=(
                    "Добавьте Qt SQL ODBC plugin (qsqlodbc) в сборку приложения "
                    "и повторите импорт."
                ),
                details=(f"Qt SQL drivers: {', '.join(available) or 'none'}",),
            )

        errors: list[str] = []
        for access_driver in self.driver_names:
            connection_name = f"geoworkbench-gs2-{uuid4().hex}"
            database = database_class.addDatabase("QODBC", connection_name)
            snapshot: AccessSnapshot | None = None
            try:
                database.setDatabaseName(
                    _odbc_connection_string(source, access_driver)
                )
                database.setConnectOptions("SQL_ATTR_LOGIN_TIMEOUT=5")
                if not database.open():
                    errors.append(
                        f"{access_driver}: {_sql_error_text(database.lastError())}"
                    )
                    continue
                snapshot = self._read_open_database(qt_sql, database)
            finally:
                database.close()
                del database
                database_class.removeDatabase(connection_name)
            if snapshot is not None:
                return snapshot

        bitness = platform.architecture()[0]
        raise Gs2MetadataBackendUnavailable(
            "access-odbc-unavailable",
            "Microsoft Access Database Engine/ODBC не открыл GS2.mdb",
            action=(
                "Установите Microsoft Access Database Engine той же разрядности, "
                f"что и приложение ({bitness}), либо проверьте регистрацию Access ODBC."
            ),
            details=tuple(errors),
        )

    def _read_open_database(self, qt_sql, database) -> AccessSnapshot:
        table_names = tuple(
            sorted(
                (
                    str(name)
                    for name in database.tables()
                    if not str(name).casefold().startswith("msys")
                ),
                key=str.casefold,
            )
        )
        tables: list[AccessTable] = []
        diagnostics: list[Gs2MetadataDiagnostic] = []
        for table_name in table_names:
            if not _is_metadata_table(table_name):
                continue
            query = qt_sql.QSqlQuery(database)
            escaped = table_name.replace("]", "]]")
            if not query.exec(f"SELECT TOP {self.row_limit} * FROM [{escaped}]"):
                diagnostics.append(
                    Gs2MetadataDiagnostic(
                        "access-table-read-failed",
                        f"Не удалось прочитать таблицу Access {table_name}",
                        "Проверьте целостность GS2.mdb и права чтения.",
                        (_sql_error_text(query.lastError()),),
                    )
                )
                continue
            record = query.record()
            column_names = tuple(
                str(record.fieldName(index)) for index in range(record.count())
            )
            rows: list[Mapping[str, object]] = []
            while query.next() and len(rows) < self.row_limit:
                rows.append(
                    {
                        column_name: query.value(index)
                        for index, column_name in enumerate(column_names)
                    }
                )
            tables.append(AccessTable(table_name, tuple(rows)))
        return AccessSnapshot(
            adapter=self.adapter_name,
            table_names=table_names,
            tables=tuple(tables),
            diagnostics=tuple(diagnostics),
        )


def read_gs2_metadata(
    source: str | Path,
    *,
    backend: AccessMetadataBackend | None = None,
) -> Gs2Metadata:
    """Read one extracted ``GS2.mdb`` without making metadata a hard blocker."""

    path = Path(source).expanduser().resolve()
    if not path.is_file():
        return _failed_metadata(
            path,
            "metadata-file-missing",
            f"Файл метаданных GS2 не найден: {path}",
            "Проверьте целостность контейнера GS2.",
        )
    try:
        snapshot = (backend or QtOdbcAccessBackend()).read(path)
    except Gs2MetadataBackendUnavailable as exc:
        return Gs2Metadata(
            source=path,
            database_member=path.name,
            state=Gs2MetadataState.UNAVAILABLE,
            diagnostics=(
                Gs2MetadataDiagnostic(
                    exc.code,
                    str(exc),
                    exc.action,
                    exc.details,
                ),
            ),
        )
    except Exception as exc:
        return _failed_metadata(
            path,
            "metadata-read-failed",
            f"Не удалось прочитать GS2.mdb: {exc}",
            (
                "Проверьте драйвер Microsoft Access, разрядность приложения "
                "и целостность базы."
            ),
            details=(f"{type(exc).__name__}: {exc}",),
        )

    channels = _extract_channels(snapshot.tables)
    formulas = _extract_formulas(snapshot.tables)
    wells = _extract_wells(snapshot.tables)
    diagnostics = list(snapshot.diagnostics)
    if not channels:
        diagnostics.append(
            Gs2MetadataDiagnostic(
                "channel-schema-not-found",
                (
                    "GS2.mdb прочитан, но явная схема соответствия каналов "
                    "не найдена"
                ),
                (
                    "Исходные имена Sxxx будут сохранены. Проверьте сопоставление "
                    "в окне импорта; формулы Access сохранены в происхождении набора."
                ),
            )
        )
    return Gs2Metadata(
        source=path,
        database_member=path.name,
        state=(
            Gs2MetadataState.PARTIAL
            if diagnostics
            else Gs2MetadataState.LOADED
        ),
        adapter=snapshot.adapter,
        database_tables=snapshot.table_names,
        channels=channels,
        formulas=formulas,
        wells=wells,
        diagnostics=tuple(diagnostics),
    )


def read_gs2_container_metadata(
    source: str | Path,
    *,
    backend: AccessMetadataBackend | None = None,
) -> Gs2Metadata:
    """Extract only ``GS2.mdb``, read it, then discard the temporary copy."""

    container = Path(source).expanduser().resolve()
    try:
        with extract_gs2_metadata(container) as (database, manifest):
            metadata = read_gs2_metadata(database, backend=backend)
            return replace(
                metadata,
                source=container,
                database_member=manifest.metadata_member.name,
            )
    except Exception as exc:
        return _failed_metadata(
            container,
            "metadata-extraction-failed",
            f"Не удалось извлечь GS2.mdb: {exc}",
            "Проверьте целостность и доступность контейнера GS2.",
            details=(f"{type(exc).__name__}: {exc}",),
        )


def channel_definitions_for_table(
    metadata: Gs2Metadata,
    field_names: tuple[str, ...],
    member_name: str,
) -> tuple[ChannelDefinition, ...]:
    """Resolve only explicit Access mappings applicable to one Paradox table."""

    fields = {name.casefold(): name for name in field_names}
    selected = _select_channels_for_table(metadata, field_names, member_name)
    definitions: list[ChannelDefinition] = []
    for source_key in fields:
        channel = selected.get(source_key)
        if channel is None:
            continue
        description = channel.description or channel.mnemonic or channel.source_name
        definitions.append(
            ChannelDefinition(
                source=fields[source_key],
                mnemonic=_safe_mnemonic(channel.mnemonic or channel.source_name),
                name_ru=description,
                name_kk=description,
                name_en=description,
                unit=channel.unit,
                category="gs2-access",
            )
        )
    return tuple(definitions)


def channel_dictionary_for_table(
    metadata: Gs2Metadata,
    field_names: tuple[str, ...],
    member_name: str,
    *,
    base: GeoScapeChannelDictionary | None = None,
    sensor_catalog: SensorCatalog | None = None,
) -> tuple[GeoScapeChannelDictionary, int, int]:
    dictionary = base or GeoScapeChannelDictionary.load()
    catalog = sensor_catalog or active_sensor_catalog()
    relations = _select_channels_for_table(metadata, field_names, member_name)
    metadata_matches = 0
    sensor_matches = 0
    for source in field_names:
        source_key = source.casefold()
        relation = relations.get(source_key)
        existing = dictionary.resolve(source)
        lookup_mnemonic = (
            relation.mnemonic
            if relation is not None and relation.mnemonic
            else source
        )
        lookup_description = relation.description if relation is not None else ""
        lookup_unit = relation.unit if relation is not None else ""
        sensor_match = catalog.match(
            lookup_mnemonic,
            description=lookup_description,
            unit=lookup_unit,
        )
        if sensor_match is None and lookup_mnemonic.casefold() != source_key:
            sensor_match = catalog.match(
                source,
                description=lookup_description,
                unit=lookup_unit,
            )
        sensor = sensor_match.definition if sensor_match is not None else None

        if relation is None:
            if existing is not None or sensor is None:
                continue
            dictionary.set_user(
                ChannelDefinition(
                    source=source,
                    mnemonic=sensor.canonical_mnemonic,
                    name_ru=sensor.name_ru,
                    name_kk=sensor.name_ru,
                    name_en=sensor.name_ru,
                    unit=sensor.unit,
                    category=f"gs2-sensors:{sensor.category}",
                )
            )
            sensor_matches += 1
            continue

        metadata_matches += 1
        relation_has_distinct_mnemonic = (
            bool(relation.mnemonic)
            and relation.mnemonic.casefold() != source_key
        )
        mnemonic = (
            relation.mnemonic
            if relation_has_distinct_mnemonic
            else existing.mnemonic
            if existing is not None
            else sensor.canonical_mnemonic
            if sensor is not None
            else source
        )
        description = (
            relation.description
            or (existing.name_ru if existing is not None else "")
            or (sensor.name_ru if sensor is not None else "")
            or source
        )
        unit = (
            relation.unit
            or (existing.unit if existing is not None else "")
            or (sensor.unit if sensor is not None else "")
        )
        dictionary.set_user(
            ChannelDefinition(
                source=source,
                mnemonic=_safe_mnemonic(mnemonic),
                name_ru=description,
                name_kk=description,
                name_en=description,
                unit=unit,
                category=(
                    f"gs2-access+sensors:{sensor.category}"
                    if sensor is not None
                    else "gs2-access"
                ),
            )
        )
        if sensor is not None and (
            not relation_has_distinct_mnemonic or not relation.unit
        ):
            sensor_matches += 1
    return dictionary, metadata_matches, sensor_matches


def _select_channels_for_table(
    metadata: Gs2Metadata,
    field_names: tuple[str, ...],
    member_name: str,
) -> dict[str, Gs2ChannelMetadata]:
    fields = {name.casefold() for name in field_names}
    target_member = _normalize_member(member_name)
    selected: dict[str, tuple[int, Gs2ChannelMetadata]] = {}
    for channel in metadata.channels:
        source_key = channel.source_name.casefold()
        if source_key not in fields:
            continue
        relation_member = _normalize_member(channel.source_member)
        if relation_member and target_member and relation_member != target_member:
            continue
        priority = 2 if relation_member else 1
        previous = selected.get(source_key)
        if previous is None or priority > previous[0]:
            selected[source_key] = (priority, channel)
    return {key: value[1] for key, value in selected.items()}


def metadata_dataset_parameters(metadata: Gs2Metadata) -> dict[str, str]:
    diagnostics = [
        {
            "code": item.code,
            "message": item.message,
            "action": item.action,
            "details": list(item.details),
        }
        for item in metadata.diagnostics
    ]
    parameters = {
        "GS2_METADATA_STATUS": metadata.state.value,
        "GS2_METADATA_ADAPTER": metadata.adapter,
        "GS2_METADATA_MEMBER": metadata.database_member,
        "GS2_METADATA_TABLE_COUNT": str(len(metadata.database_tables)),
        "GS2_METADATA_TABLES": "; ".join(metadata.database_tables),
        "GS2_METADATA_CHANNEL_COUNT": str(len(metadata.channels)),
        "GS2_METADATA_FORMULA_COUNT": str(len(metadata.formulas)),
        "GS2_METADATA_DIAGNOSTICS": json.dumps(
            diagnostics,
            ensure_ascii=False,
            sort_keys=True,
        ),
        "GS2_CHANNEL_RELATIONS": json.dumps(
            [
                {
                    "source": item.source_name,
                    "mnemonic": item.mnemonic,
                    "unit": item.unit,
                    "description": _bounded_text(item.description),
                    "parameter_id": item.parameter_id,
                    "source_member": item.source_member,
                    "subset": item.subset,
                    "origin_table": item.origin_table,
                }
                for item in metadata.channels[:1_000]
            ],
            ensure_ascii=False,
            sort_keys=True,
        ),
        "GS2_FORMULAS": json.dumps(
            [
                {
                    "name": _bounded_text(item.name),
                    "expression": _bounded_text(item.expression),
                    "description": _bounded_text(item.description),
                    "parameter_id": item.parameter_id,
                    "subset": item.subset,
                }
                for item in metadata.formulas[:1_000]
            ],
            ensure_ascii=False,
            sort_keys=True,
        ),
    }
    well = metadata.primary_well
    if well is not None:
        parameters.update(
            {
                "GS2_WELL_ID": well.identifier,
                "GS2_WELL_UID": well.uid,
                "GS2_WELL_NAME": well.name,
                "GS2_COUNTRY": well.country,
                "GS2_FIELD": well.field,
                "GS2_AREA": well.area,
                "GS2_COMPANY": well.company,
                "GS2_STATION_MODEL": well.station_model,
            }
        )
    return parameters


def metadata_well_headers(metadata: Gs2Metadata) -> dict[str, str]:
    well = metadata.primary_well
    if well is None:
        return {}
    return {
        key: value
        for key, value in {
            "WELL": well.name,
            "FLD": well.field,
            "LOC": well.area,
            "CTRY": well.country,
            "COMP": well.company,
        }.items()
        if value
    }


def annotate_gs2_dataset(
    dataset: Dataset,
    metadata: Gs2Metadata,
    member_name: str,
) -> int:
    """Attach exact Access relation evidence to curves already created."""

    source_names = tuple(
        curve.metadata.semantic.source_mnemonic
        for curve in dataset.curves.values()
        if curve.metadata.semantic is not None
    )
    relations = _select_channels_for_table(metadata, source_names, member_name)
    annotated = 0
    for curve in dataset.curves.values():
        semantic = curve.metadata.semantic
        if semantic is None:
            continue
        relation = relations.get(semantic.source_mnemonic.casefold())
        if relation is None:
            continue
        evidence = (
            f"GS2.mdb table={relation.origin_table or 'unknown'}; "
            f"parameter_id={relation.parameter_id or relation.source_name}"
        )
        semantic_evidence = semantic.evidence
        if evidence not in semantic_evidence:
            semantic = replace(
                semantic,
                evidence=(*semantic_evidence, evidence),
            )
        provenance_token = (
            f"gs2-mdb:{relation.origin_table or 'unknown'}:"
            f"{relation.parameter_id or relation.source_name}"
        )
        provenance = curve.metadata.provenance
        if provenance_token not in provenance:
            provenance = f"{provenance}|{provenance_token}"
        curve.metadata = replace(
            curve.metadata,
            provenance=provenance,
            semantic=semantic,
        )
        annotated += 1
    return annotated


def _extract_channels(
    tables: tuple[AccessTable, ...],
) -> tuple[Gs2ChannelMetadata, ...]:
    channels: dict[tuple[str, str], Gs2ChannelMetadata] = {}
    for table in tables:
        normalized_table = _normalize_key(table.name)
        if (
            normalized_table != "FORMULAS"
            and not any(token in normalized_table for token in _METADATA_TABLE_TOKENS)
        ):
            continue
        for row in table.rows:
            parameter_id = (
                _text_value(row, ("RESGID",))
                if normalized_table == "FORMULAS"
                else _text_value(row, ("PARAMETERID", "CHANNELID"))
            )
            source = _text_value(
                row,
                (
                    "SOURCEFIELD",
                    "SOURCENAME",
                    "FIELDNAME",
                    "COLUMNNAME",
                    "CHANNELCODE",
                    "PARAMETERCODE",
                    "CURVECODE",
                    "SENSORCODE",
                    "SIGNALCODE",
                    "CODE",
                ),
            )
            mnemonic = _text_value(
                row,
                ("LASMNEMONIC", "MNEMONIC", "SHORTNAME", "CHANNELMNEMONIC"),
            )
            formula_name = _text_value(row, ("FORMULANAME",))
            if normalized_table == "FORMULAS":
                identifier = _clean_identifier(parameter_id)
                if not identifier.isdigit():
                    continue
                source = f"S{identifier}"
            elif not source:
                candidate = mnemonic or formula_name
                if candidate and _TECHNICAL_CHANNEL.fullmatch(candidate):
                    source = candidate
            if not source or not _TECHNICAL_CHANNEL.fullmatch(source):
                continue
            description = _text_value(
                row,
                (
                    "DESCRIPTION",
                    "DISPLAYNAME",
                    "CHANNELNAME",
                    "PARAMETERNAME",
                    "CURVENAME",
                    "SENSORNAME",
                    "NAME",
                ),
            )
            if normalized_table == "FORMULAS" and formula_name:
                description = formula_name
            if (
                not description
                and formula_name
                and formula_name.casefold() != source.casefold()
            ):
                description = formula_name
            source_member = _text_value(
                row,
                (
                    "SOURCEMEMBER",
                    "MEMBERNAME",
                    "DATAFILE",
                    "TABLENAME",
                    "SOURCEARRAY",
                ),
            )
            if not source_member:
                table_id = _text_value(row, ("TABLEID", "DATASETID"))
                if table_id and _clean_identifier(table_id).isdigit():
                    source_member = f"GS2#{_clean_identifier(table_id)}"
            channel = Gs2ChannelMetadata(
                source_name=source,
                mnemonic=mnemonic or source,
                unit=_text_value(
                    row,
                    ("UNIT", "UNITS", "UNITNAME", "MEASUREUNIT", "UOM"),
                ),
                description=description,
                parameter_id=parameter_id,
                source_member=source_member,
                subset=_text_value(row, ("SUBSET", "SUBSETID")),
                origin_table=table.name,
            )
            key = (
                channel.source_name.casefold(),
                _normalize_member(channel.source_member),
            )
            previous = channels.get(key)
            if previous is None or _channel_score(channel) > _channel_score(previous):
                channels[key] = channel
    return tuple(
        sorted(
            channels.values(),
            key=lambda item: (
                _normalize_member(item.source_member),
                item.source_name.casefold(),
            ),
        )
    )


def _extract_formulas(
    tables: tuple[AccessTable, ...],
) -> tuple[Gs2FormulaMetadata, ...]:
    formulas: list[Gs2FormulaMetadata] = []
    for table in tables:
        if _normalize_key(table.name) != "FORMULAS":
            continue
        for row in table.rows:
            name = _text_value(row, ("FORMULANAME", "NAME"))
            expression = _text_value(row, ("FORMULATEXT", "EXPRESSION", "FORMULA"))
            if not name and not expression:
                continue
            formulas.append(
                Gs2FormulaMetadata(
                    name=name,
                    expression=expression,
                    description=_text_value(row, ("DESCRIPTION",)),
                    parameter_id=_text_value(
                        row,
                        ("RESGID", "PARAMETERID", "CHANNELID"),
                    ),
                    subset=_text_value(row, ("SUBSET", "SUBSETID")),
                )
            )
    return tuple(formulas)


def _extract_wells(
    tables: tuple[AccessTable, ...],
) -> tuple[Gs2WellMetadata, ...]:
    wells: list[Gs2WellMetadata] = []
    accepted = {"WELL", "WELLINFO", "WELLINFORMATION", "WELLS"}
    for table in tables:
        if _normalize_key(table.name) not in accepted:
            continue
        for row in table.rows:
            oilfield = _text_value(
                row,
                ("OILFIELD", "OILFIELDNAME", "DEPOSIT", "DEPOSITNAME"),
            )
            field_value = _text_value(row, ("FIELD", "FIELDNAME"))
            area = (
                field_value
                if oilfield and field_value and field_value != oilfield
                else _text_value(
                    row,
                    ("AREA", "AREANAME", "OBJECT", "OBJECTNAME", "BLOCK"),
                )
            )
            well = Gs2WellMetadata(
                identifier=_text_value(row, ("WELLID", "ID", "GUID")),
                uid=_text_value(row, ("UID", "WELLUID")),
                name=_text_value(
                    row,
                    ("WELLNAME", "WELL", "WELLNO", "WELLNUMBER", "NAME", "NUMBER"),
                ),
                country=_text_value(row, ("COUNTRY", "COUNTRYNAME")),
                field=oilfield or field_value,
                area=area,
                company=_text_value(
                    row,
                    (
                        "COMPANY",
                        "COMPANYNAME",
                        "CUSTOMER",
                        "CLIENT",
                        "SERVICECOMPANY",
                    ),
                ),
                station_model=_text_value(
                    row,
                    ("STATIONMODEL", "STATION", "LOGGERMODEL"),
                ),
                origin_table=table.name,
            )
            if any(
                (
                    well.identifier,
                    well.uid,
                    well.name,
                    well.country,
                    well.field,
                    well.area,
                    well.company,
                    well.station_model,
                )
            ):
                wells.append(well)
    return tuple(wells)


def _is_metadata_table(name: str) -> bool:
    normalized = _normalize_key(name)
    return normalized in _METADATA_TABLE_NAMES or any(
        token in normalized for token in _METADATA_TABLE_TOKENS
    )


def _text_value(row: Mapping[str, object], aliases: tuple[str, ...]) -> str:
    normalized = {
        _normalize_key(str(key)): value
        for key, value in row.items()
    }
    for alias in aliases:
        value = normalized.get(alias)
        if value is None:
            continue
        text = str(value).strip().strip("\x00")
        if text:
            return text
    return ""


def _normalize_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", value.upper())


def _clean_identifier(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return text.casefold()
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _normalize_member(member_name: str) -> str:
    if not member_name.strip():
        return ""
    stem = PurePosixPath(member_name.replace("\\", "/")).stem
    match = _GS2_TABLE_ID.match(stem)
    if match is not None:
        return f"gs2#{match.group('identifier')}"
    identifier = _clean_identifier(stem)
    return f"gs2#{identifier}" if identifier.isdigit() else stem.casefold()


def _channel_score(channel: Gs2ChannelMetadata) -> int:
    return sum(
        bool(value)
        for value in (
            channel.mnemonic,
            channel.unit,
            channel.description,
            channel.parameter_id,
            channel.source_member,
            channel.subset,
        )
    )


def _safe_mnemonic(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_")
    return (normalized or "CURVE")[:32]


def _bounded_text(value: str, limit: int = 2_048) -> str:
    return value if len(value) <= limit else f"{value[:limit]}…"


def _odbc_connection_string(source: Path, access_driver: str) -> str:
    driver = access_driver.replace("}", "}}")
    # The Access ODBC driver accepts braces around DRIVER, but treats braces
    # around DBQ as literal filename characters and rejects the path with
    # S1000 "invalid file name".
    return f"DRIVER={{{driver}}};DBQ={source};READONLY=TRUE;"


def _sql_error_text(error: object) -> str:
    text_method = getattr(error, "text", None)
    if callable(text_method):
        text = str(text_method()).strip()
        if text:
            return text
    return str(error).strip() or "unknown ODBC error"


def _failed_metadata(
    source: Path,
    code: str,
    message: str,
    action: str,
    *,
    details: tuple[str, ...] = (),
) -> Gs2Metadata:
    return Gs2Metadata(
        source=source,
        database_member=source.name,
        state=Gs2MetadataState.FAILED,
        diagnostics=(
            Gs2MetadataDiagnostic(code, message, action, details),
        ),
    )


__all__ = [
    "AccessMetadataBackend",
    "AccessSnapshot",
    "AccessTable",
    "Gs2ChannelMetadata",
    "Gs2FormulaMetadata",
    "Gs2Metadata",
    "Gs2MetadataBackendUnavailable",
    "Gs2MetadataDiagnostic",
    "Gs2MetadataState",
    "Gs2WellMetadata",
    "QtOdbcAccessBackend",
    "annotate_gs2_dataset",
    "channel_definitions_for_table",
    "channel_dictionary_for_table",
    "metadata_dataset_parameters",
    "metadata_well_headers",
    "read_gs2_container_metadata",
    "read_gs2_metadata",
]
