from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
from typing import Iterable, Iterator
from uuid import UUID
import xml.etree.ElementTree as ET
import zipfile


_WITSML_V2_NAMESPACE = "http://www.energistics.org/energyml/data/witsmlv2"
_XML_SUFFIXES = {".xml", ".witsml"}
_FORBIDDEN_XML_DECLARATIONS = (b"<!doctype", b"<!entity")
_VERSION_PATTERN = re.compile(r"^2(?:\.\d+){0,2}$")
_SAFE_UUID_PATTERN = re.compile(r"^[0-9a-fA-F-]{32,36}$")


class WitsmlInventoryError(ValueError):
    """Raised when an offline source cannot be inventoried as WITSML 2.x."""


@dataclass(frozen=True, slots=True)
class WitsmlInventoryLimits:
    """Resource limits for XML files and ZIP/EPC packages."""

    max_files: int = 5_000
    max_file_size: int = 64 * 1024**2
    max_total_size: int = 512 * 1024**2
    max_compression_ratio: float = 500.0
    max_elements: int = 500_000

    def __post_init__(self) -> None:
        for value, name in (
            (self.max_files, "max_files"),
            (self.max_file_size, "max_file_size"),
            (self.max_total_size, "max_total_size"),
            (self.max_elements, "max_elements"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} должен быть положительным целым числом")
        if (
            isinstance(self.max_compression_ratio, bool)
            or not isinstance(self.max_compression_ratio, (int, float))
            or float(self.max_compression_ratio) <= 0.0
        ):
            raise ValueError("max_compression_ratio должен быть положительным числом")


@dataclass(frozen=True, slots=True)
class WitsmlDiagnostic:
    source_name: str
    severity: str
    message: str

    def __post_init__(self) -> None:
        if self.severity not in {"info", "warning", "error"}:
            raise ValueError("severity должен быть info, warning или error")


@dataclass(frozen=True, slots=True)
class WitsmlReference:
    relation: str
    content_type: str | None
    title: str | None
    uuid: str | None


@dataclass(frozen=True, slots=True)
class WitsmlChannelIndex:
    index_type: str | None
    mnemonic: str | None
    uom: str | None
    direction: str | None
    datum_reference: str | None

    @property
    def display_text(self) -> str:
        parts = [
            self.mnemonic or self.index_type or "index",
            self.uom or "",
            self.direction or "",
        ]
        return " / ".join(part for part in parts if part)


@dataclass(frozen=True, slots=True)
class WitsmlChannelSummary:
    mnemonic: str | None
    data_type: str | None
    uom: str | None
    source: str | None
    time_depth: str | None
    logging_method: str | None
    channel_class: str | None
    indexes: tuple[WitsmlChannelIndex, ...]
    start_index: str | None
    end_index: str | None


@dataclass(frozen=True, slots=True)
class WitsmlObjectSummary:
    source_name: str
    object_type: str
    namespace: str
    schema_version: str | None
    uuid: str | None
    uid: str | None
    title: str | None
    description: str | None
    growing_status: str | None
    references: tuple[WitsmlReference, ...]
    channel: WitsmlChannelSummary | None = None
    element_count: int = 0


@dataclass(frozen=True, slots=True)
class WitsmlInventory:
    source: Path
    objects: tuple[WitsmlObjectSummary, ...]
    diagnostics: tuple[WitsmlDiagnostic, ...]

    @property
    def channels(self) -> tuple[WitsmlObjectSummary, ...]:
        return tuple(item for item in self.objects if item.channel is not None)

    @property
    def schema_versions(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    item.schema_version
                    for item in self.objects
                    if item.schema_version is not None
                }
            )
        )

    @property
    def type_counts(self) -> dict[str, int]:
        return dict(Counter(item.object_type for item in self.objects))


@dataclass(frozen=True, slots=True)
class _XmlSource:
    name: str
    payload: bytes


def inspect_witsml(
    source: str | Path,
    *,
    limits: WitsmlInventoryLimits | None = None,
) -> WitsmlInventory:
    """Build a read-only WITSML 2.x object and channel inventory.

    The function accepts one XML/WITSML file, a directory of XML files, or a
    ZIP/EPC package. Archives are inspected in memory and are never extracted.
    """

    path = Path(source).expanduser().resolve()
    safety = limits or WitsmlInventoryLimits()
    xml_sources = tuple(_iter_xml_sources(path, safety))
    if not xml_sources:
        raise WitsmlInventoryError("В источнике не найдены XML-файлы WITSML")

    objects: list[WitsmlObjectSummary] = []
    diagnostics: list[WitsmlDiagnostic] = []
    for item in xml_sources:
        try:
            summary, item_diagnostics = _parse_witsml_object(item, safety)
        except WitsmlInventoryError as exc:
            diagnostics.append(WitsmlDiagnostic(item.name, "error", str(exc)))
            continue
        objects.append(summary)
        diagnostics.extend(item_diagnostics)

    if not objects:
        details = diagnostics[0].message if diagnostics else "неизвестная ошибка"
        raise WitsmlInventoryError(
            f"Не найдено ни одного корректного объекта WITSML 2.x: {details}"
        )

    _append_duplicate_uuid_diagnostics(objects, diagnostics)
    objects.sort(key=lambda item: (item.object_type.casefold(), item.source_name.casefold()))
    diagnostics.sort(key=lambda item: (item.severity, item.source_name.casefold(), item.message))
    return WitsmlInventory(path, tuple(objects), tuple(diagnostics))


def _iter_xml_sources(path: Path, limits: WitsmlInventoryLimits) -> Iterator[_XmlSource]:
    if path.is_dir():
        candidates = sorted(
            (
                item
                for item in path.rglob("*")
                if item.is_file() and item.suffix.casefold() in _XML_SUFFIXES
            ),
            key=lambda item: item.as_posix().casefold(),
        )
        if len(candidates) > limits.max_files:
            raise WitsmlInventoryError(
                f"Слишком много XML-файлов: {len(candidates)} > {limits.max_files}"
            )
        total_size = 0
        for item in candidates:
            size = item.stat().st_size
            _validate_member_size(item.name, size, limits)
            total_size += size
            if total_size > limits.max_total_size:
                raise WitsmlInventoryError("Общий размер XML превышает безопасный лимит")
            try:
                payload = item.read_bytes()
            except OSError as exc:
                raise WitsmlInventoryError(f"Не удалось прочитать {item}: {exc}") from exc
            yield _XmlSource(item.relative_to(path).as_posix(), payload)
        return

    if not path.is_file():
        raise WitsmlInventoryError(f"Источник WITSML не найден: {path}")

    if zipfile.is_zipfile(path):
        yield from _iter_zip_xml_sources(path, limits)
        return

    size = path.stat().st_size
    _validate_member_size(path.name, size, limits)
    try:
        yield _XmlSource(path.name, path.read_bytes())
    except OSError as exc:
        raise WitsmlInventoryError(f"Не удалось прочитать {path}: {exc}") from exc


def _iter_zip_xml_sources(
    path: Path,
    limits: WitsmlInventoryLimits,
) -> Iterator[_XmlSource]:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            if len(infos) > limits.max_files:
                raise WitsmlInventoryError(
                    f"Слишком много элементов в архиве: {len(infos)} > {limits.max_files}"
                )
            normalized_names: set[str] = set()
            xml_infos: list[tuple[str, zipfile.ZipInfo]] = []
            total_size = 0
            for info in infos:
                name = _safe_archive_member_name(info.filename)
                folded = name.casefold()
                if folded in normalized_names:
                    raise WitsmlInventoryError(
                        f"Повторяющийся путь внутри архива: {name}"
                    )
                normalized_names.add(folded)
                if info.flag_bits & 0x1:
                    raise WitsmlInventoryError(
                        f"Зашифрованный элемент не поддерживается: {name}"
                    )
                if info.is_dir():
                    continue
                _validate_member_size(name, info.file_size, limits)
                ratio = info.file_size / max(1, info.compress_size)
                if ratio > limits.max_compression_ratio:
                    raise WitsmlInventoryError(
                        f"Подозрительно высокий коэффициент сжатия: {name}"
                    )
                total_size += info.file_size
                if total_size > limits.max_total_size:
                    raise WitsmlInventoryError(
                        "Распакованный архив превышает безопасный лимит"
                    )
                if PurePosixPath(name).suffix.casefold() in _XML_SUFFIXES:
                    xml_infos.append((name, info))

            for name, info in sorted(xml_infos, key=lambda item: item[0].casefold()):
                with archive.open(info, "r") as stream:
                    payload = stream.read(limits.max_file_size + 1)
                if len(payload) > limits.max_file_size:
                    raise WitsmlInventoryError(
                        f"XML-файл превышает безопасный лимит: {name}"
                    )
                yield _XmlSource(name, payload)
    except WitsmlInventoryError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise WitsmlInventoryError(f"Не удалось прочитать архив WITSML: {exc}") from exc


def _parse_witsml_object(
    source: _XmlSource,
    limits: WitsmlInventoryLimits,
) -> tuple[WitsmlObjectSummary, tuple[WitsmlDiagnostic, ...]]:
    payload = source.payload
    lowered = payload[: min(len(payload), 256 * 1024)].lower()
    if any(token in lowered for token in _FORBIDDEN_XML_DECLARATIONS):
        raise WitsmlInventoryError(
            "DTD и пользовательские XML entity запрещены для офлайн-импорта"
        )
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise WitsmlInventoryError(f"Некорректный XML: {exc}") from exc

    namespace, object_type = _split_tag(root.tag)
    if namespace != _WITSML_V2_NAMESPACE:
        raise WitsmlInventoryError(
            f"Корневой namespace не является WITSML 2.x: {namespace or 'отсутствует'}"
        )

    elements = tuple(root.iter())
    if len(elements) > limits.max_elements:
        raise WitsmlInventoryError(
            f"Слишком много XML-элементов: {len(elements)} > {limits.max_elements}"
        )

    schema_version = _clean_text(root.attrib.get("schemaVersion"))
    diagnostics: list[WitsmlDiagnostic] = []
    if schema_version is None:
        diagnostics.append(
            WitsmlDiagnostic(
                source.name,
                "warning",
                "У корневого объекта отсутствует schemaVersion; namespace распознан как WITSML 2.x",
            )
        )
    elif not _VERSION_PATTERN.fullmatch(schema_version):
        raise WitsmlInventoryError(
            f"Неподдерживаемая schemaVersion WITSML: {schema_version}"
        )

    uuid = _clean_text(root.attrib.get("uuid"))
    uid = _clean_text(root.attrib.get("uid"))
    if uuid is None:
        diagnostics.append(
            WitsmlDiagnostic(
                source.name,
                "warning",
                "У top-level объекта отсутствует обязательный UUID",
            )
        )
    elif not _is_valid_uuid(uuid):
        diagnostics.append(
            WitsmlDiagnostic(
                source.name,
                "warning",
                f"UUID имеет нестандартный формат: {uuid}",
            )
        )

    citation = _direct_child(root, "Citation")
    title = _descendant_text(citation, "Title") if citation is not None else None
    description = (
        _descendant_text(citation, "Description") if citation is not None else None
    )
    growing_status = _child_text(root, "GrowingStatus")
    references = _collect_references(root)
    channel = _channel_summary(root) if object_type == "Channel" else None

    return (
        WitsmlObjectSummary(
            source_name=source.name,
            object_type=object_type,
            namespace=namespace,
            schema_version=schema_version,
            uuid=uuid,
            uid=uid,
            title=title,
            description=description,
            growing_status=growing_status,
            references=references,
            channel=channel,
            element_count=len(elements),
        ),
        tuple(diagnostics),
    )


def _channel_summary(root: ET.Element) -> WitsmlChannelSummary:
    indexes: list[WitsmlChannelIndex] = []
    for element in _direct_children(root, "Index"):
        indexes.append(
            WitsmlChannelIndex(
                index_type=_child_text(element, "IndexType"),
                mnemonic=_child_text(element, "Mnemonic"),
                uom=_child_text(element, "Uom"),
                direction=_child_text(element, "Direction"),
                datum_reference=_reference_text(element, "DatumReference"),
            )
        )

    channel_class = _direct_child(root, "ChannelClass")
    return WitsmlChannelSummary(
        mnemonic=_child_text(root, "Mnemonic"),
        data_type=_child_text(root, "DataType"),
        uom=_child_text(root, "Uom"),
        source=_child_text(root, "Source"),
        time_depth=_child_text(root, "TimeDepth"),
        logging_method=_child_text(root, "LoggingMethod"),
        channel_class=(
            _descendant_text(channel_class, "Title")
            if channel_class is not None
            else None
        ),
        indexes=tuple(indexes),
        start_index=_index_value_text(_direct_child(root, "StartIndex")),
        end_index=_index_value_text(_direct_child(root, "EndIndex")),
    )


def _collect_references(root: ET.Element) -> tuple[WitsmlReference, ...]:
    references: list[WitsmlReference] = []
    for child in root:
        relation = _split_tag(child.tag)[1]
        content_type = _descendant_text(child, "ContentType")
        uuid = _descendant_text(child, "Uuid")
        if content_type is None and uuid is None:
            continue
        references.append(
            WitsmlReference(
                relation=relation,
                content_type=content_type,
                title=_descendant_text(child, "Title"),
                uuid=uuid,
            )
        )
    return tuple(references)


def _append_duplicate_uuid_diagnostics(
    objects: Iterable[WitsmlObjectSummary],
    diagnostics: list[WitsmlDiagnostic],
) -> None:
    grouped: dict[str, list[WitsmlObjectSummary]] = {}
    for item in objects:
        if item.uuid is not None:
            grouped.setdefault(item.uuid.casefold(), []).append(item)
    for same_uuid in grouped.values():
        if len(same_uuid) < 2:
            continue
        sources = ", ".join(item.source_name for item in same_uuid)
        for item in same_uuid:
            diagnostics.append(
                WitsmlDiagnostic(
                    item.source_name,
                    "warning",
                    f"UUID повторяется в нескольких объектах пакета: {sources}",
                )
            )


def _safe_archive_member_name(raw_name: str) -> str:
    normalized = raw_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or any(":" in part for part in path.parts)
    ):
        raise WitsmlInventoryError(
            f"Небезопасный путь внутри архива: {raw_name!r}"
        )
    return path.as_posix()


def _validate_member_size(
    name: str,
    size: int,
    limits: WitsmlInventoryLimits,
) -> None:
    if size > limits.max_file_size:
        raise WitsmlInventoryError(
            f"XML-файл превышает безопасный лимит: {name}"
        )


def _split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{") and "}" in tag:
        namespace, local = tag[1:].split("}", 1)
        return namespace, local
    return "", tag


def _direct_children(element: ET.Element, local_name: str) -> tuple[ET.Element, ...]:
    return tuple(child for child in element if _split_tag(child.tag)[1] == local_name)


def _direct_child(element: ET.Element, local_name: str) -> ET.Element | None:
    return next(iter(_direct_children(element, local_name)), None)


def _child_text(element: ET.Element, local_name: str) -> str | None:
    child = _direct_child(element, local_name)
    return _clean_text(child.text) if child is not None else None


def _descendant_text(element: ET.Element | None, local_name: str) -> str | None:
    if element is None:
        return None
    for child in element.iter():
        if child is element:
            continue
        if _split_tag(child.tag)[1] == local_name:
            value = _clean_text(child.text)
            if value is not None:
                return value
    return None


def _reference_text(element: ET.Element, local_name: str) -> str | None:
    child = _direct_child(element, local_name)
    if child is None:
        return None
    return (
        _clean_text(child.text)
        or _descendant_text(child, "Title")
        or _descendant_text(child, "Uuid")
    )


def _index_value_text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    direct = _clean_text(element.text)
    if direct is not None:
        return direct
    for child in element.iter():
        if child is element:
            continue
        value = _clean_text(child.text)
        if value is not None:
            uom = _clean_text(child.attrib.get("uom"))
            return f"{value} {uom}".strip() if uom else value
    return None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _is_valid_uuid(value: str) -> bool:
    if not _SAFE_UUID_PATTERN.fullmatch(value):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True
