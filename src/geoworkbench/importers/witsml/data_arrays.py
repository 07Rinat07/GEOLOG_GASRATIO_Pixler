from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterator
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

from geoworkbench.services.bounded_input import (
    BoundedXmlError,
    InputLimitError,
    XmlInputLimits,
    parse_bounded_xml_stream,
)


WITSML_V2_NAMESPACE = "http://www.energistics.org/energyml/data/witsmlv2"
COMMON_V2_NAMESPACE = "http://www.energistics.org/energyml/data/commonv2"
_XML_SUFFIXES = {".xml", ".witsml"}
_NUMERIC_TYPES = {"byte", "bytes", "double", "float", "int", "long"}


class WitsmlDataError(ValueError):
    """Raised when WITSML channel-set bulk data cannot be read safely."""


class WitsmlDataSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class WitsmlDataLimits:
    max_files: int = 5_000
    max_xml_size: int = 64 * 1024**2
    max_external_data_size: int = 256 * 1024**2
    max_total_size: int = 768 * 1024**2
    max_compression_ratio: float = 500.0
    max_elements: int = 500_000
    max_depth: int = 128
    max_text_bytes: int = 64 * 1024**2
    max_attributes: int = 1_000_000
    max_attribute_bytes: int = 64 * 1024**2
    max_attributes_per_element: int = 256
    max_rows: int = 2_000_000
    max_cells: int = 40_000_000
    max_diagnostics: int = 2_000

    def __post_init__(self) -> None:
        integer_fields = (
            "max_files",
            "max_xml_size",
            "max_external_data_size",
            "max_total_size",
            "max_elements",
            "max_depth",
            "max_text_bytes",
            "max_attributes",
            "max_attribute_bytes",
            "max_attributes_per_element",
            "max_rows",
            "max_cells",
            "max_diagnostics",
        )
        for name in integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if (
            isinstance(self.max_compression_ratio, bool)
            or not isinstance(self.max_compression_ratio, (int, float))
            or float(self.max_compression_ratio) <= 0.0
        ):
            raise ValueError("max_compression_ratio must be positive")


@dataclass(frozen=True, slots=True)
class WitsmlDataIssue:
    code: str
    severity: WitsmlDataSeverity
    message: str
    source_name: str
    row_number: int | None = None
    channel_key: str | None = None


@dataclass(frozen=True, slots=True)
class WitsmlIndexSpec:
    key: str
    position: int
    mnemonic: str
    index_type: str
    uom: str | None
    direction: str | None
    datum_reference: str | None

    @property
    def is_time(self) -> bool:
        token = self.index_type.casefold()
        mnemonic = self.mnemonic.casefold()
        return "time" in token or "date" in token or mnemonic in {"time", "datetime", "date"}

    @property
    def is_depth(self) -> bool:
        token = self.index_type.casefold()
        mnemonic = self.mnemonic.casefold()
        return "depth" in token or mnemonic in {"md", "dept", "depth", "tvd", "tvdss"}


@dataclass(frozen=True, slots=True)
class WitsmlChannelSpec:
    key: str
    position: int
    uuid: str | None
    mnemonic: str
    title: str | None
    description: str | None
    data_type: str
    uom: str | None
    source: str | None
    time_depth: str | None
    logging_method: str | None
    channel_class: str | None
    point_metadata_count: int

    @property
    def is_scalar_numeric(self) -> bool:
        return self.data_type.casefold() in _NUMERIC_TYPES and self.point_metadata_count == 0


@dataclass(frozen=True, slots=True)
class WitsmlDataRow:
    index_values: tuple[Any | None, ...]
    channel_values: tuple[Any | None, ...]


@dataclass(frozen=True, slots=True)
class WitsmlChannelSetData:
    source: Path
    source_name: str
    schema_version: str | None
    uuid: str | None
    title: str
    description: str | None
    wellbore_title: str | None
    wellbore_uuid: str | None
    indexes: tuple[WitsmlIndexSpec, ...]
    channels: tuple[WitsmlChannelSpec, ...]
    rows: tuple[WitsmlDataRow, ...]
    issues: tuple[WitsmlDataIssue, ...]
    source_sha256: str
    data_sha256: str

    @property
    def key(self) -> str:
        return self.uuid or f"{self.source_name}#{self.title}"

    @property
    def importable_channel_count(self) -> int:
        return sum(item.is_scalar_numeric for item in self.channels)


@dataclass(frozen=True, slots=True)
class WitsmlDataPackage:
    source: Path
    channel_sets: tuple[WitsmlChannelSetData, ...]
    issues: tuple[WitsmlDataIssue, ...]


@dataclass(frozen=True, slots=True)
class _XmlDocument:
    name: str
    path: Path | None = None
    archive_member: str | None = None


class _SourceAccessor:
    def __init__(self, source: Path, limits: WitsmlDataLimits) -> None:
        self.source = source
        self.limits = limits
        self._archive: zipfile.ZipFile | None = None
        self._archive_infos: dict[str, zipfile.ZipInfo] = {}
        self._directory_root: Path | None = None

    def __enter__(self) -> _SourceAccessor:
        if self.source.is_dir():
            self._directory_root = self.source
            return self
        if not self.source.is_file():
            raise WitsmlDataError(f"WITSML source not found: {self.source}")
        if zipfile.is_zipfile(self.source):
            self._archive = zipfile.ZipFile(self.source, "r")
            infos = self._archive.infolist()
            if len(infos) > self.limits.max_files:
                raise WitsmlDataError("WITSML package contains too many members")
            total = 0
            for info in infos:
                name = _safe_member_name(info.filename)
                folded = name.casefold()
                if folded in self._archive_infos:
                    raise WitsmlDataError(f"Duplicate package member: {name}")
                if info.flag_bits & 0x1:
                    raise WitsmlDataError(f"Encrypted package member is unsupported: {name}")
                if info.is_dir():
                    continue
                total += info.file_size
                if total > self.limits.max_total_size:
                    raise WitsmlDataError("WITSML package exceeds the total size limit")
                compressed = max(info.compress_size, 1)
                if info.file_size / compressed > self.limits.max_compression_ratio:
                    raise WitsmlDataError(f"Suspicious compression ratio: {name}")
                self._archive_infos[folded] = info
        return self

    def __exit__(self, *_args: object) -> None:
        if self._archive is not None:
            self._archive.close()

    def iter_xml_documents(self) -> Iterator[_XmlDocument]:
        if self._archive is not None:
            for info in sorted(self._archive_infos.values(), key=lambda item: item.filename.casefold()):
                name = _safe_member_name(info.filename)
                if PurePosixPath(name).suffix.casefold() not in _XML_SUFFIXES:
                    continue
                if info.file_size > self.limits.max_xml_size:
                    raise WitsmlDataError(f"XML member exceeds size limit: {name}")
                yield _XmlDocument(name, archive_member=info.filename)
            return
        if self._directory_root is not None:
            candidates = sorted(
                (item for item in self._directory_root.rglob("*") if item.is_file() and item.suffix.casefold() in _XML_SUFFIXES),
                key=lambda item: item.as_posix().casefold(),
            )
            if len(candidates) > self.limits.max_files:
                raise WitsmlDataError("WITSML directory contains too many XML files")
            total = 0
            for item in candidates:
                size = item.stat().st_size
                if size > self.limits.max_xml_size:
                    raise WitsmlDataError(f"XML file exceeds size limit: {item.name}")
                total += size
                if total > self.limits.max_total_size:
                    raise WitsmlDataError("WITSML directory exceeds total size limit")
                yield _XmlDocument(item.relative_to(self._directory_root).as_posix(), path=item)
            return
        if self.source.stat().st_size > self.limits.max_xml_size:
            raise WitsmlDataError("WITSML XML file exceeds size limit")
        yield _XmlDocument(self.source.name, path=self.source)

    @contextmanager
    def open_xml(self, document: _XmlDocument) -> Iterator[BinaryIO]:
        if document.archive_member is not None:
            if self._archive is None:
                raise WitsmlDataError("WITSML archive is not open")
            with self._archive.open(document.archive_member, "r") as stream:
                yield stream
            return
        if document.path is None:
            raise WitsmlDataError(f"XML source is unavailable: {document.name}")
        with document.path.open("rb") as stream:
            yield stream

    def hash_xml(self, document: _XmlDocument) -> str:
        digest = sha256()
        total = 0
        with self.open_xml(document) as stream:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > self.limits.max_xml_size:
                    raise WitsmlDataError(f"XML file exceeds size limit: {document.name}")
                digest.update(chunk)
        return digest.hexdigest()

    def read_relative(self, document_name: str, uri: str) -> tuple[str, bytes]:
        member_name = _resolve_relative_name(document_name, uri)
        if self._archive is not None:
            info = self._archive_infos.get(member_name.casefold())
            if info is None:
                raise WitsmlDataError(f"External ChannelData file not found: {member_name}")
            if info.file_size > self.limits.max_external_data_size:
                raise WitsmlDataError(f"External ChannelData exceeds size limit: {member_name}")
            return member_name, self._archive.read(info)
        if self._directory_root is not None:
            target = (self._directory_root / PurePosixPath(member_name)).resolve()
            root = self._directory_root.resolve()
        else:
            target = (self.source.parent / PurePosixPath(member_name)).resolve()
            root = self.source.parent.resolve()
        if target != root and root not in target.parents:
            raise WitsmlDataError("External ChannelData path escapes the WITSML source root")
        if not target.is_file():
            raise WitsmlDataError(f"External ChannelData file not found: {member_name}")
        if target.stat().st_size > self.limits.max_external_data_size:
            raise WitsmlDataError(f"External ChannelData exceeds size limit: {member_name}")
        return member_name, target.read_bytes()


def read_witsml_channel_sets(
    source: str | Path,
    *,
    limits: WitsmlDataLimits | None = None,
) -> WitsmlDataPackage:
    """Read embedded or relative-file WITSML 2.x ChannelSet data arrays.

    The supported on-disk bulk representation is the JSON-compatible array layout
    defined for ``ChannelData/Data``. Binary Avro ``FileUri`` payloads are reported as
    unsupported rather than guessed.
    """

    path = Path(source).expanduser().resolve()
    safety = limits or WitsmlDataLimits()
    channel_sets: list[WitsmlChannelSetData] = []
    package_issues: list[WitsmlDataIssue] = []

    with _SourceAccessor(path, safety) as accessor:
        documents = tuple(accessor.iter_xml_documents())
        if not documents:
            raise WitsmlDataError("No WITSML XML documents were found")
        for document in documents:
            try:
                root = _parse_xml(document, safety, accessor)
            except WitsmlDataError as exc:
                _append_issue(
                    package_issues,
                    WitsmlDataIssue("invalid-xml", WitsmlDataSeverity.ERROR, str(exc), document.name),
                    safety,
                )
                continue
            namespace, object_type = _split_tag(root.tag)
            if namespace != WITSML_V2_NAMESPACE:
                continue
            schema_version = (root.attrib.get("schemaVersion") or "").strip() or None
            candidates: tuple[ET.Element, ...]
            if object_type == "ChannelSet":
                candidates = (root,)
            elif object_type == "Log":
                candidates = _direct_children(root, "ChannelSet")
            else:
                continue
            for position, element in enumerate(candidates, start=1):
                try:
                    parsed = _parse_channel_set(
                        path,
                        document,
                        element,
                        accessor,
                        safety,
                        schema_version=schema_version,
                        ordinal=position,
                    )
                except WitsmlDataError as exc:
                    _append_issue(
                        package_issues,
                        WitsmlDataIssue(
                            "invalid-channel-set",
                            WitsmlDataSeverity.ERROR,
                            str(exc),
                            document.name,
                        ),
                        safety,
                    )
                    continue
                channel_sets.append(parsed)

    if not channel_sets:
        detail = package_issues[0].message if package_issues else "no Log/ChannelSet data objects"
        raise WitsmlDataError(f"No readable WITSML ChannelSet data arrays: {detail}")
    channel_sets.sort(key=lambda item: (item.source_name.casefold(), item.title.casefold(), item.key))
    return WitsmlDataPackage(path, tuple(channel_sets), tuple(package_issues))


def _parse_channel_set(
    source: Path,
    document: _XmlDocument,
    element: ET.Element,
    accessor: _SourceAccessor,
    limits: WitsmlDataLimits,
    *,
    schema_version: str | None,
    ordinal: int,
) -> WitsmlChannelSetData:
    namespace, local = _split_tag(element.tag)
    if namespace != WITSML_V2_NAMESPACE or local != "ChannelSet":
        raise WitsmlDataError("Expected a WITSML 2.x ChannelSet element")
    version = (element.attrib.get("schemaVersion") or schema_version or "").strip() or None
    if version is not None and not version.startswith("2"):
        raise WitsmlDataError(f"Unsupported ChannelSet schemaVersion: {version}")
    title = _citation_text(element, "Title") or f"ChannelSet {ordinal}"
    description = _citation_text(element, "Description")
    uuid = (element.attrib.get("uuid") or element.attrib.get("uid") or "").strip() or None
    indexes = tuple(_parse_index(item, position) for position, item in enumerate(_direct_children(element, "Index")))
    channels = tuple(_parse_channel(item, position) for position, item in enumerate(_direct_children(element, "Channel")))
    if not indexes:
        raise WitsmlDataError(f"ChannelSet {title!r} has no Index metadata")
    if not channels:
        raise WitsmlDataError(f"ChannelSet {title!r} has no Channel metadata")

    issues: list[WitsmlDataIssue] = []
    data_container = _direct_child(element, "Data")
    if data_container is None:
        _append_issue(
            issues,
            WitsmlDataIssue("missing-data", WitsmlDataSeverity.WARNING, "ChannelSet has no bulk Data element", document.name),
            limits,
        )
        payload = b"[]"
    else:
        embedded_element = _direct_child(data_container, "Data")
        embedded = (
            embedded_element.text
            if embedded_element is not None
            and embedded_element.text is not None
            and embedded_element.text.strip()
            else None
        )
        file_uri = _child_text(data_container, "FileUri")
        if embedded is not None and file_uri:
            _append_issue(
                issues,
                WitsmlDataIssue(
                    "data-and-file-uri",
                    WitsmlDataSeverity.WARNING,
                    "Both Data and FileUri are present; FileUri takes precedence",
                    document.name,
                ),
                limits,
            )
        if file_uri:
            resolved_name, payload = accessor.read_relative(document.name, file_uri)
            suffix = PurePosixPath(resolved_name).suffix.casefold()
            if suffix in {".avro", ".bin"}:
                raise WitsmlDataError(
                    f"Binary external ChannelData is not supported yet: {resolved_name}"
                )
        elif embedded is not None:
            payload = embedded.encode("utf-8")
        else:
            raise WitsmlDataError("ChannelData requires Data or FileUri")

    rows, row_issues = _parse_rows(payload, document.name, indexes, channels, limits)
    issues.extend(row_issues)
    wellbore = _direct_child(element, "Wellbore")
    wellbore_title = _reference_text(wellbore, "Title") if wellbore is not None else None
    wellbore_uuid = _reference_text(wellbore, "Uuid") if wellbore is not None else None
    source_hash = accessor.hash_xml(document)
    data_hash = sha256(payload).hexdigest()
    return WitsmlChannelSetData(
        source=source,
        source_name=document.name,
        schema_version=version,
        uuid=uuid,
        title=title,
        description=description,
        wellbore_title=wellbore_title,
        wellbore_uuid=wellbore_uuid,
        indexes=indexes,
        channels=channels,
        rows=rows,
        issues=tuple(issues),
        source_sha256=source_hash,
        data_sha256=data_hash,
    )


def _parse_index(element: ET.Element, position: int) -> WitsmlIndexSpec:
    mnemonic = _child_text(element, "Mnemonic") or f"INDEX_{position + 1}"
    index_type = _child_text(element, "IndexType") or "generic"
    uom = _child_text(element, "Uom")
    direction = _child_text(element, "Direction")
    datum = _reference_text(_direct_child(element, "DatumReference"), "Title")
    if datum is None:
        datum = _child_text(element, "DatumReference")
    key = f"index:{position}:{mnemonic.strip().upper()}"
    return WitsmlIndexSpec(key, position, mnemonic.strip(), index_type.strip(), uom, direction, datum)


def _parse_channel(element: ET.Element, position: int) -> WitsmlChannelSpec:
    mnemonic = _child_text(element, "Mnemonic") or f"CHANNEL_{position + 1}"
    uuid = (element.attrib.get("uuid") or element.attrib.get("uid") or "").strip() or None
    key = uuid or f"channel:{position}:{mnemonic.strip().upper()}"
    channel_class = _reference_text(_direct_child(element, "ChannelClass"), "Title")
    return WitsmlChannelSpec(
        key=key,
        position=position,
        uuid=uuid,
        mnemonic=mnemonic.strip(),
        title=_citation_text(element, "Title"),
        description=_citation_text(element, "Description"),
        data_type=(_child_text(element, "DataType") or "null").strip(),
        uom=_child_text(element, "Uom"),
        source=_child_text(element, "Source"),
        time_depth=_child_text(element, "TimeDepth"),
        logging_method=_child_text(element, "LoggingMethod"),
        channel_class=channel_class,
        point_metadata_count=len(_direct_children(element, "PointMetadata")),
    )


def _parse_rows(
    payload: bytes,
    source_name: str,
    indexes: tuple[WitsmlIndexSpec, ...],
    channels: tuple[WitsmlChannelSpec, ...],
    limits: WitsmlDataLimits,
) -> tuple[tuple[WitsmlDataRow, ...], tuple[WitsmlDataIssue, ...]]:
    if len(payload) > limits.max_external_data_size:
        raise WitsmlDataError("ChannelData payload exceeds size limit")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise WitsmlDataError("ChannelData is not UTF-8 JSON text") from exc
    try:
        raw = json.loads(text, parse_constant=lambda value: (_raise_json_constant(value)))
    except (json.JSONDecodeError, ValueError) as exc:
        raise WitsmlDataError(f"Invalid ChannelData JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise WitsmlDataError("ChannelData top-level value must be an array")
    if len(raw) > limits.max_rows:
        raise WitsmlDataError("ChannelData exceeds the row limit")
    expected_cells = len(raw) * (len(indexes) + len(channels))
    if expected_cells > limits.max_cells:
        raise WitsmlDataError("ChannelData exceeds the cell limit")

    rows: list[WitsmlDataRow] = []
    issues: list[WitsmlDataIssue] = []
    for row_number, item in enumerate(raw, start=1):
        if not isinstance(item, list) or len(item) != 2:
            _append_issue(
                issues,
                WitsmlDataIssue(
                    "invalid-row-layout",
                    WitsmlDataSeverity.ERROR,
                    "A data row must be [[index values], [channel values]]",
                    source_name,
                    row_number=row_number,
                ),
                limits,
            )
            continue
        raw_indexes, raw_channels = item
        if not isinstance(raw_indexes, list) or not isinstance(raw_channels, list):
            _append_issue(
                issues,
                WitsmlDataIssue(
                    "invalid-row-arrays",
                    WitsmlDataSeverity.ERROR,
                    "Index and channel sections must both be arrays",
                    source_name,
                    row_number=row_number,
                ),
                limits,
            )
            continue
        if len(raw_indexes) > len(indexes) or len(raw_channels) > len(channels):
            _append_issue(
                issues,
                WitsmlDataIssue(
                    "row-too-wide",
                    WitsmlDataSeverity.ERROR,
                    "A data row contains more values than declared metadata",
                    source_name,
                    row_number=row_number,
                ),
                limits,
            )
            continue
        index_values = tuple(raw_indexes) + (None,) * (len(indexes) - len(raw_indexes))
        channel_values = tuple(raw_channels) + (None,) * (len(channels) - len(raw_channels))
        for index_spec, index_value in zip(indexes, index_values, strict=True):
            if not _valid_index_value(index_spec, index_value):
                _append_issue(
                    issues,
                    WitsmlDataIssue(
                        "invalid-index-value",
                        WitsmlDataSeverity.ERROR,
                        f"Invalid value for index {index_spec.mnemonic}: {index_value!r}",
                        source_name,
                        row_number=row_number,
                    ),
                    limits,
                )
            elif (
                index_spec.is_time
                and isinstance(index_value, str)
                and not _has_utc_offset(index_value)
            ):
                _append_issue(
                    issues,
                    WitsmlDataIssue(
                        "non-utc-time-index",
                        WitsmlDataSeverity.WARNING,
                        f"Time index {index_spec.mnemonic} is not expressed as UTC and will be normalized",
                        source_name,
                        row_number=row_number,
                    ),
                    limits,
                )
        for channel_spec, channel_value in zip(channels, channel_values, strict=True):
            if not _valid_channel_value(channel_spec, channel_value):
                _append_issue(
                    issues,
                    WitsmlDataIssue(
                        "invalid-channel-value",
                        WitsmlDataSeverity.WARNING,
                        f"Invalid value for channel {channel_spec.mnemonic}: {channel_value!r}",
                        source_name,
                        row_number=row_number,
                        channel_key=channel_spec.key,
                    ),
                    limits,
                )
        # Preserve rows with invalid index values so Import Review can report,
        # count and (when explicitly enabled) drop them atomically.  Structural
        # row errors above cannot be represented safely and remain parser issues.
        rows.append(WitsmlDataRow(index_values, channel_values))
    return tuple(rows), tuple(issues)


def _valid_index_value(spec: WitsmlIndexSpec, value: Any | None) -> bool:
    if value is None:
        return False
    if spec.is_time:
        return isinstance(value, str) and _parse_utc_datetime(value) is not None
    return _finite_number(value)


def _valid_channel_value(spec: WitsmlChannelSpec, value: Any | None) -> bool:
    if value is None:
        return True
    kind = spec.data_type.casefold()
    if spec.point_metadata_count:
        return isinstance(value, list) and bool(value)
    if kind in _NUMERIC_TYPES:
        return _finite_number(value)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    if kind == "vector":
        return isinstance(value, list) and all(_finite_number(item) for item in value)
    if kind == "null":
        return value is None
    return False



def _has_utc_offset(value: str) -> bool:
    text = value.strip().upper()
    return text.endswith("Z") or text.endswith("+00:00") or text.endswith("+0000")

def parse_witsml_utc_datetime(value: str) -> datetime:
    parsed = _parse_utc_datetime(value)
    if parsed is None:
        raise WitsmlDataError(f"Invalid WITSML UTC timestamp: {value!r}")
    return parsed


def _parse_utc_datetime(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    offset = parsed.utcoffset()
    if offset is None:
        return None
    return parsed.astimezone(timezone.utc)


def _parse_xml(
    document: _XmlDocument,
    limits: WitsmlDataLimits,
    accessor: _SourceAccessor,
) -> ET.Element:
    xml_limits = XmlInputLimits(
        max_bytes=limits.max_xml_size,
        max_depth=limits.max_depth,
        max_elements=limits.max_elements,
        max_text_bytes=limits.max_text_bytes,
        max_attributes=limits.max_attributes,
        max_attribute_bytes=limits.max_attribute_bytes,
        max_attributes_per_element=limits.max_attributes_per_element,
    )
    try:
        with accessor.open_xml(document) as stream:
            root = parse_bounded_xml_stream(
                stream,
                limits=xml_limits,
                source_name=document.name,
            )
    except (OSError, RuntimeError, BoundedXmlError, InputLimitError) as exc:
        raise WitsmlDataError(
            f"Invalid or forbidden XML in {document.name}: {exc}"
        ) from exc
    namespace, _local = _split_tag(root.tag)
    if namespace != WITSML_V2_NAMESPACE:
        raise WitsmlDataError(f"Document is not WITSML 2.x: {document.name}")
    version = (root.attrib.get("schemaVersion") or "").strip()
    if version and not version.startswith("2"):
        raise WitsmlDataError(f"Unsupported schemaVersion {version!r}: {document.name}")
    return root


def _safe_member_name(raw_name: str) -> str:
    normalized = raw_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise WitsmlDataError(f"Unsafe package member path: {raw_name}")
    return path.as_posix()


def _resolve_relative_name(document_name: str, uri: str) -> str:
    parts = urlsplit(uri.strip())
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise WitsmlDataError(f"Only relative FileUri values are supported: {uri}")
    decoded = unquote(parts.path).replace("\\", "/")
    candidate = PurePosixPath(document_name).parent / PurePosixPath(decoded)
    normalized_parts: list[str] = []
    for part in candidate.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not normalized_parts:
                raise WitsmlDataError(f"FileUri escapes package root: {uri}")
            normalized_parts.pop()
            continue
        normalized_parts.append(part)
    if not normalized_parts:
        raise WitsmlDataError(f"Invalid FileUri: {uri}")
    return PurePosixPath(*normalized_parts).as_posix()


def _direct_children(element: ET.Element, local_name: str) -> tuple[ET.Element, ...]:
    return tuple(item for item in element if _split_tag(item.tag)[1] == local_name)


def _direct_child(element: ET.Element, local_name: str) -> ET.Element | None:
    return next((item for item in element if _split_tag(item.tag)[1] == local_name), None)


def _child_text(element: ET.Element, local_name: str) -> str | None:
    child = _direct_child(element, local_name)
    return _clean_text(child.text if child is not None else None)


def _citation_text(element: ET.Element, local_name: str) -> str | None:
    citation = next((item for item in element if _split_tag(item.tag)[1] == "Citation"), None)
    if citation is None:
        return None
    return _child_text(citation, local_name)


def _reference_text(element: ET.Element | None, local_name: str) -> str | None:
    if element is None:
        return None
    direct = _child_text(element, local_name)
    if direct is not None:
        return direct
    for item in element.iter():
        if item is element:
            continue
        if _split_tag(item.tag)[1] == local_name:
            return _clean_text(item.text)
    return None


def _split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{") and "}" in tag:
        namespace, local = tag[1:].split("}", 1)
        return namespace, local
    return "", tag


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned or None


def _finite_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and isfinite(float(value))


def _raise_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value}")


def _append_issue(
    issues: list[WitsmlDataIssue],
    issue: WitsmlDataIssue,
    limits: WitsmlDataLimits,
) -> None:
    if len(issues) < limits.max_diagnostics:
        issues.append(issue)
