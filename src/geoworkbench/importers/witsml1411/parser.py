from __future__ import annotations

import csv
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from pathlib import Path
import re
from typing import Iterable
import xml.etree.ElementTree as ET

from geoworkbench.importers.witsml import (
    WitsmlChannelSetData,
    WitsmlChannelSpec,
    WitsmlDataIssue,
    WitsmlDataRow,
    WitsmlDataSeverity,
    WitsmlIndexSpec,
)
from geoworkbench.importers.witsml1411.models import (
    Witsml1411Capabilities,
    Witsml1411LogCurve,
    Witsml1411LogData,
    Witsml1411LogHeader,
    Witsml1411Well,
    Witsml1411Wellbore,
)
from geoworkbench.importers.witsml1411.queries import WITSML_1SERIES_NAMESPACE


_FORBIDDEN_XML = (b"<!doctype", b"<!entity")
_NUMERIC_TYPES = {"byte", "short", "int", "integer", "long", "float", "double", "decimal"}


class Witsml1411ParseError(ValueError):
    pass


def parse_capabilities(xml_text: str, data_version: str) -> Witsml1411Capabilities:
    root = _parse_xml(xml_text, expected_roots={"capServers", "capServer"})
    cap = root if _local(root.tag) == "capServer" else _first_child(root, "capServer")
    if cap is None:
        raise Witsml1411ParseError("Capabilities response has no capServer object")
    functions: list[str] = []
    data_objects: list[str] = []
    for item in cap.iter():
        local = _local(item.tag)
        if local == "function":
            name = (item.attrib.get("name") or _text(item)).strip()
            if name:
                functions.append(name)
        elif local == "dataObject":
            name = (item.attrib.get("name") or _text(item)).strip()
            if name:
                data_objects.append(name)
    return Witsml1411Capabilities(
        data_version=data_version,
        description=_child_text(cap, "description"),
        vendor=_child_text(cap, "vendor"),
        functions=tuple(dict.fromkeys(functions)),
        data_objects=tuple(dict.fromkeys(data_objects)),
        raw_xml=xml_text,
    )


def parse_wells(xml_text: str) -> tuple[Witsml1411Well, ...]:
    root = _parse_xml(xml_text, expected_roots={"wells"})
    result: list[Witsml1411Well] = []
    for element in _children(root, "well"):
        uid = (element.attrib.get("uid") or "").strip()
        name = _child_text(element, "name") or uid
        if uid:
            result.append(
                Witsml1411Well(
                    uid=uid,
                    name=name,
                    field=_child_text(element, "field"),
                    operator=_child_text(element, "operator"),
                    d_tim_last_change=_child_text(element, "dTimLastChange"),
                )
            )
    return tuple(result)


def parse_wellbores(xml_text: str) -> tuple[Witsml1411Wellbore, ...]:
    root = _parse_xml(xml_text, expected_roots={"wellbores"})
    result: list[Witsml1411Wellbore] = []
    for element in _children(root, "wellbore"):
        uid = (element.attrib.get("uid") or "").strip()
        uid_well = (element.attrib.get("uidWell") or "").strip()
        name = _child_text(element, "name") or uid
        if uid and uid_well:
            result.append(
                Witsml1411Wellbore(
                    uid=uid,
                    uid_well=uid_well,
                    name=name,
                    name_well=_child_text(element, "nameWell"),
                    status=_child_text(element, "statusWellbore"),
                    purpose=_child_text(element, "purposeWellbore"),
                    d_tim_last_change=_child_text(element, "dTimLastChange"),
                )
            )
    return tuple(result)


def parse_logs(xml_text: str) -> tuple[Witsml1411LogHeader, ...]:
    root = _parse_xml(xml_text, expected_roots={"logs"})
    return tuple(_parse_log_header(item) for item in _children(root, "log"))


def parse_log_data(xml_text: str) -> Witsml1411LogData:
    root = _parse_xml(xml_text, expected_roots={"logs"})
    log = _first_child(root, "log")
    if log is None:
        raise Witsml1411ParseError("LogData response has no log object")
    header = _parse_log_header(log)
    blocks = tuple(_children(log, "logData"))
    if not blocks:
        raise Witsml1411ParseError("Log response has no logData")
    mnemonic_list: tuple[str, ...] | None = None
    unit_list: tuple[str | None, ...] | None = None
    rows: list[tuple[str | None, ...]] = []
    for block in blocks:
        current_mnemonics = _split_list(_child_text(block, "mnemonicList"))
        current_units = tuple(item or None for item in _split_list(_child_text(block, "unitList")))
        if not current_mnemonics:
            raise Witsml1411ParseError("logData mnemonicList is empty")
        if mnemonic_list is None:
            mnemonic_list = current_mnemonics
            unit_list = _pad_tuple(current_units, len(current_mnemonics), None)
        elif current_mnemonics != mnemonic_list:
            raise Witsml1411ParseError("logData blocks use different mnemonicList values")
        for data_element in _children(block, "data"):
            parsed = next(csv.reader([_text(data_element)], skipinitialspace=False), [])
            row = tuple(_clean_cell(value) for value in parsed)
            rows.append(_pad_tuple(row, len(mnemonic_list), None))
    assert mnemonic_list is not None and unit_list is not None
    return Witsml1411LogData(
        header=header,
        mnemonic_list=mnemonic_list,
        unit_list=unit_list,
        rows=tuple(rows),
        raw_xml=xml_text,
        source_sha256=sha256(xml_text.encode("utf-8")).hexdigest(),
    )


def log_data_to_channel_set(
    data: Witsml1411LogData,
    *,
    endpoint_label: str,
) -> WitsmlChannelSetData:
    if not data.mnemonic_list:
        raise Witsml1411ParseError("LogData has no mnemonics")
    index_position = _index_position(data.header, data.mnemonic_list)
    index_mnemonic = data.mnemonic_list[index_position]
    index_unit = data.unit_list[index_position] if index_position < len(data.unit_list) else None
    index_type = _normalized_index_type(data.header.index_type, index_mnemonic)
    indexes = (
        WitsmlIndexSpec(
            key=f"witsml1411:index:{index_mnemonic}",
            position=0,
            mnemonic=index_mnemonic,
            index_type=index_type,
            uom=None if "time" in index_type else index_unit,
            direction=data.header.direction,
            datum_reference=None,
        ),
    )
    curve_by_mnemonic = {item.mnemonic.casefold(): item for item in data.header.curves}
    channels: list[WitsmlChannelSpec] = []
    source_positions: list[int] = []
    for source_position, mnemonic in enumerate(data.mnemonic_list):
        if source_position == index_position:
            continue
        metadata = curve_by_mnemonic.get(mnemonic.casefold())
        unit = data.unit_list[source_position] if source_position < len(data.unit_list) else None
        data_type = (metadata.type_log_data if metadata else None) or "double"
        channels.append(
            WitsmlChannelSpec(
                key=f"witsml1411:curve:{mnemonic}:{source_position}",
                position=len(channels),
                uuid=metadata.uid if metadata else None,
                mnemonic=mnemonic,
                title=metadata.curve_description if metadata else mnemonic,
                description=metadata.curve_description if metadata else None,
                data_type=_normalized_data_type(data_type),
                uom=unit or (metadata.unit if metadata else None),
                source="WITSML 1.4.1.1 SOAP",
                time_depth=data.header.index_type,
                logging_method=None,
                channel_class=None,
                point_metadata_count=0,
            )
        )
        source_positions.append(source_position)
    issues: list[WitsmlDataIssue] = []
    converted_rows: list[WitsmlDataRow] = []
    null_values = {
        item.mnemonic.casefold(): item.null_value
        for item in data.header.curves
        if item.null_value is not None
    }
    for row_number, row in enumerate(data.rows, start=1):
        index_raw = row[index_position] if index_position < len(row) else None
        index_value = _convert_index(index_raw, index_type)
        if index_value is None:
            issues.append(
                WitsmlDataIssue(
                    "invalid-index-value",
                    WitsmlDataSeverity.WARNING,
                    f"Row {row_number} has an invalid index value",
                    endpoint_label,
                    row_number=row_number,
                )
            )
        values: list[object | None] = []
        for channel, position in zip(channels, source_positions, strict=True):
            raw = row[position] if position < len(row) else None
            null_marker = null_values.get(channel.mnemonic.casefold())
            if raw is None or (null_marker is not None and raw.strip() == null_marker.strip()):
                values.append(None)
                continue
            if channel.is_scalar_numeric:
                try:
                    values.append(float(raw))
                except ValueError:
                    values.append(None)
                    issues.append(
                        WitsmlDataIssue(
                            "invalid-channel-value",
                            WitsmlDataSeverity.WARNING,
                            f"Invalid numeric value for {channel.mnemonic}: {raw!r}",
                            endpoint_label,
                            row_number=row_number,
                            channel_key=channel.key,
                        )
                    )
            else:
                values.append(raw)
        converted_rows.append(WitsmlDataRow((index_value,), tuple(values)))
    data_material = "\n".join(
        ",".join("" if value is None else str(value) for value in row)
        for row in data.rows
    ).encode("utf-8")
    safe_source = Path("witsml1411_remote.xml")
    return WitsmlChannelSetData(
        source=safe_source,
        source_name=endpoint_label,
        schema_version="1.4.1.1",
        uuid=data.header.uid,
        title=data.header.name,
        description="Imported from a read-only WITSML 1.4.1.1 SOAP log",
        wellbore_title=data.header.name_wellbore,
        wellbore_uuid=data.header.uid_wellbore,
        indexes=indexes,
        channels=tuple(channels),
        rows=tuple(converted_rows),
        issues=tuple(issues),
        source_sha256=data.source_sha256,
        data_sha256=sha256(data_material).hexdigest(),
    )


def _parse_log_header(element: ET.Element) -> Witsml1411LogHeader:
    curves: list[Witsml1411LogCurve] = []
    for item in _children(element, "logCurveInfo"):
        mnemonic = _child_text(item, "mnemonic") or ""
        if not mnemonic:
            continue
        curves.append(
            Witsml1411LogCurve(
                uid=(item.attrib.get("uid") or "").strip() or None,
                mnemonic=mnemonic,
                unit=_child_text(item, "unit"),
                curve_description=_child_text(item, "curveDescription"),
                type_log_data=_child_text(item, "typeLogData"),
                min_index=_child_text(item, "minIndex"),
                max_index=_child_text(item, "maxIndex"),
                null_value=_child_text(item, "nullValue"),
            )
        )
    return Witsml1411LogHeader(
        uid=(element.attrib.get("uid") or "").strip(),
        uid_well=(element.attrib.get("uidWell") or "").strip(),
        uid_wellbore=(element.attrib.get("uidWellbore") or "").strip(),
        name=_child_text(element, "name") or (element.attrib.get("uid") or "log"),
        name_well=_child_text(element, "nameWell"),
        name_wellbore=_child_text(element, "nameWellbore"),
        index_type=_child_text(element, "indexType"),
        index_curve=_child_text(element, "indexCurve"),
        start_index=_measure_text(element, "startIndex"),
        end_index=_measure_text(element, "endIndex"),
        start_datetime_index=_child_text(element, "startDateTimeIndex"),
        end_datetime_index=_child_text(element, "endDateTimeIndex"),
        direction=_child_text(element, "direction"),
        curves=tuple(curves),
        d_tim_last_change=_child_text(element, "dTimLastChange"),
    )


def _parse_xml(xml_text: str, *, expected_roots: set[str]) -> ET.Element:
    payload = xml_text.encode("utf-8")
    lowered = payload[:8192].lower()
    if any(marker in lowered for marker in _FORBIDDEN_XML):
        raise Witsml1411ParseError("WITSML XML contains a forbidden DTD/entity declaration")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise Witsml1411ParseError(f"Invalid WITSML XML: {exc}") from exc
    namespace, local = _split_tag(root.tag)
    if local not in expected_roots:
        raise Witsml1411ParseError(f"Unexpected WITSML root: {local}")
    if namespace and namespace != WITSML_1SERIES_NAMESPACE:
        raise Witsml1411ParseError(f"Unexpected WITSML namespace: {namespace}")
    return root


def _index_position(header: Witsml1411LogHeader, mnemonics: tuple[str, ...]) -> int:
    if header.index_curve:
        for position, mnemonic in enumerate(mnemonics):
            if mnemonic.casefold() == header.index_curve.casefold():
                return position
    return 0


def _normalized_index_type(index_type: str | None, mnemonic: str) -> str:
    token = " ".join(filter(None, (index_type, mnemonic))).casefold()
    if "date time" in token or "datetime" in token or mnemonic.casefold() in {"time", "datetime"}:
        return "date time"
    if "measured depth" in token or mnemonic.casefold() in {"dept", "depth", "md"}:
        return "measured depth"
    if "vertical depth" in token or mnemonic.casefold() in {"tvd", "tvdss"}:
        return "vertical depth"
    return index_type or mnemonic


def _normalized_data_type(value: str) -> str:
    token = value.strip().casefold()
    if token in _NUMERIC_TYPES:
        return "double"
    if token in {"boolean", "bool"}:
        return "boolean"
    return "string"


def _convert_index(value: str | None, index_type: str) -> object | None:
    if value is None:
        return None
    if "time" in index_type.casefold() or "date" in index_type.casefold():
        return value
    try:
        return float(value)
    except ValueError:
        return None


def _split_list(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item.strip() for item in next(csv.reader([value]), []) if item.strip())


def _clean_cell(value: str) -> str | None:
    token = value.strip()
    return token if token else None


def _pad_tuple(values: tuple, size: int, fill):
    if len(values) >= size:
        return tuple(values[:size])
    return tuple(values) + (fill,) * (size - len(values))


def _measure_text(parent: ET.Element, local_name: str) -> str | None:
    item = _first_child(parent, local_name)
    return _text(item) if item is not None else None


def _child_text(parent: ET.Element, local_name: str) -> str | None:
    item = _first_child(parent, local_name)
    if item is None:
        return None
    value = _text(item).strip()
    return value or None


def _first_child(parent: ET.Element, local_name: str) -> ET.Element | None:
    return next((item for item in parent if _local(item.tag) == local_name), None)


def _children(parent: ET.Element, local_name: str) -> list[ET.Element]:
    return [item for item in parent if _local(item.tag) == local_name]


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext())


def _split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{") and "}" in tag:
        namespace, local = tag[1:].split("}", 1)
        return namespace, local
    return "", tag


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
