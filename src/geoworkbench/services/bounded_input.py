from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
import xml.etree.ElementTree as ET
from xml.parsers import expat


_DEFAULT_CHUNK_SIZE = 64 * 1024


class InputLimitError(ValueError):
    """Raised when an untrusted input exceeds an explicit resource limit."""

    def __init__(
        self,
        source_name: str,
        limit_name: str,
        actual: int,
        limit: int,
    ) -> None:
        self.source_name = source_name
        self.limit_name = limit_name
        self.actual = actual
        self.limit = limit
        super().__init__(
            f"{source_name}: {limit_name} limit exceeded ({actual} > {limit})"
        )


class BoundedXmlError(ValueError):
    """Raised when XML is malformed, unsafe, or exceeds parser limits."""


@dataclass(frozen=True, slots=True)
class BinaryInputLimits:
    max_bytes: int
    chunk_size: int = _DEFAULT_CHUNK_SIZE

    def __post_init__(self) -> None:
        _positive_int(self.max_bytes, "max_bytes")
        _positive_int(self.chunk_size, "chunk_size")


@dataclass(frozen=True, slots=True)
class XmlInputLimits:
    """Streaming XML resource limits applied before a full tree can materialize."""

    max_bytes: int
    max_depth: int = 128
    max_elements: int = 500_000
    max_text_bytes: int = 64 * 1024**2
    max_attributes: int = 1_000_000
    max_attribute_bytes: int = 64 * 1024**2
    max_attributes_per_element: int = 256
    chunk_size: int = _DEFAULT_CHUNK_SIZE

    def __post_init__(self) -> None:
        for value, name in (
            (self.max_bytes, "max_bytes"),
            (self.max_depth, "max_depth"),
            (self.max_elements, "max_elements"),
            (self.max_text_bytes, "max_text_bytes"),
            (self.max_attributes, "max_attributes"),
            (self.max_attribute_bytes, "max_attribute_bytes"),
            (self.max_attributes_per_element, "max_attributes_per_element"),
            (self.chunk_size, "chunk_size"),
        ):
            _positive_int(value, name)


def read_bounded_path(
    path: str | Path,
    *,
    limits: BinaryInputLimits,
) -> bytes:
    source = Path(path)
    size = source.stat().st_size
    if size > limits.max_bytes:
        raise InputLimitError(str(source), "bytes", size, limits.max_bytes)
    with source.open("rb") as stream:
        return read_bounded_binary(
            stream,
            limits=limits,
            source_name=str(source),
        )


def read_bounded_binary(
    stream: BinaryIO,
    *,
    limits: BinaryInputLimits,
    source_name: str = "input",
) -> bytes:
    """Read bytes incrementally and stop as soon as the configured cap is crossed."""

    payload = bytearray()
    total = 0
    while True:
        remaining_probe = limits.max_bytes - total + 1
        chunk = stream.read(min(limits.chunk_size, remaining_probe))
        if not chunk:
            break
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise TypeError("bounded binary reader requires a byte stream")
        raw = bytes(chunk)
        total += len(raw)
        if total > limits.max_bytes:
            raise InputLimitError(source_name, "bytes", total, limits.max_bytes)
        payload.extend(raw)
    return bytes(payload)


def parse_bounded_xml_bytes(
    payload: bytes,
    *,
    limits: XmlInputLimits,
    source_name: str = "XML input",
) -> ET.Element:
    return parse_bounded_xml_stream(
        BytesIO(payload),
        limits=limits,
        source_name=source_name,
    )


def parse_bounded_xml_text(
    text: str,
    *,
    limits: XmlInputLimits,
    source_name: str = "XML input",
) -> ET.Element:
    return parse_bounded_xml_bytes(
        text.encode("utf-8"),
        limits=limits,
        source_name=source_name,
    )


def parse_bounded_xml_stream(
    stream: BinaryIO,
    *,
    limits: XmlInputLimits,
    source_name: str = "XML input",
) -> ET.Element:
    """Build an ElementTree with Expat while enforcing limits during parsing.

    DTDs, entity declarations, external entities and notations are rejected before
    expansion. Size, nesting depth, element count, text volume and attribute volume
    are checked in callbacks, so malicious inputs are stopped before a complete tree
    or expanded text can be retained in memory.
    """

    parser = expat.ParserCreate(namespace_separator="}")
    parser.buffer_text = True
    parser.ordered_attributes = False
    parser.specified_attributes = True
    try:
        parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    except AttributeError:  # pragma: no cover - supported by CPython's Expat
        pass

    stack: list[ET.Element] = []
    root: ET.Element | None = None
    text_target: tuple[ET.Element, bool] | None = None
    byte_count = 0
    element_count = 0
    text_byte_count = 0
    attribute_count = 0
    attribute_byte_count = 0

    def reject_declaration(*_args: object) -> None:
        raise BoundedXmlError(
            f"{source_name}: DTD, entity and notation declarations are forbidden"
        )

    def qname(name: str) -> str:
        if "}" not in name:
            return name
        namespace, local = name.split("}", 1)
        return f"{{{namespace}}}{local}"

    def start_element(name: str, attributes: dict[str, str]) -> None:
        nonlocal root, text_target, element_count, attribute_count, attribute_byte_count
        depth = len(stack) + 1
        if depth > limits.max_depth:
            raise InputLimitError(source_name, "XML depth", depth, limits.max_depth)

        element_count += 1
        if element_count > limits.max_elements:
            raise InputLimitError(
                source_name,
                "XML elements",
                element_count,
                limits.max_elements,
            )

        current_attributes = len(attributes)
        if current_attributes > limits.max_attributes_per_element:
            raise InputLimitError(
                source_name,
                "attributes per element",
                current_attributes,
                limits.max_attributes_per_element,
            )
        attribute_count += current_attributes
        if attribute_count > limits.max_attributes:
            raise InputLimitError(
                source_name,
                "XML attributes",
                attribute_count,
                limits.max_attributes,
            )

        normalized_attributes: dict[str, str] = {}
        for key, value in attributes.items():
            normalized_key = qname(key)
            normalized_attributes[normalized_key] = value
            attribute_byte_count += len(normalized_key.encode("utf-8"))
            attribute_byte_count += len(value.encode("utf-8"))
            if attribute_byte_count > limits.max_attribute_bytes:
                raise InputLimitError(
                    source_name,
                    "XML attribute bytes",
                    attribute_byte_count,
                    limits.max_attribute_bytes,
                )

        element = ET.Element(qname(name), normalized_attributes)
        if stack:
            stack[-1].append(element)
        elif root is None:
            root = element
        else:
            raise BoundedXmlError(f"{source_name}: XML contains multiple root elements")
        stack.append(element)
        text_target = (element, False)

    def end_element(_name: str) -> None:
        nonlocal text_target
        if not stack:
            raise BoundedXmlError(f"{source_name}: XML element stack is inconsistent")
        element = stack.pop()
        text_target = (element, True)

    def character_data(data: str) -> None:
        nonlocal text_byte_count
        if not data or text_target is None:
            return
        text_byte_count += len(data.encode("utf-8"))
        if text_byte_count > limits.max_text_bytes:
            raise InputLimitError(
                source_name,
                "XML text bytes",
                text_byte_count,
                limits.max_text_bytes,
            )
        element, is_tail = text_target
        if is_tail:
            element.tail = (element.tail or "") + data
        else:
            element.text = (element.text or "") + data

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.CharacterDataHandler = character_data
    parser.StartDoctypeDeclHandler = reject_declaration
    parser.EntityDeclHandler = reject_declaration
    parser.UnparsedEntityDeclHandler = reject_declaration
    parser.NotationDeclHandler = reject_declaration

    def reject_external_entity(*_args: object) -> int:
        reject_declaration()
        return 0

    parser.ExternalEntityRefHandler = reject_external_entity

    try:
        while True:
            remaining_probe = limits.max_bytes - byte_count + 1
            chunk = stream.read(min(limits.chunk_size, remaining_probe))
            if not chunk:
                break
            if not isinstance(chunk, (bytes, bytearray, memoryview)):
                raise TypeError("bounded XML parser requires a byte stream")
            raw = bytes(chunk)
            byte_count += len(raw)
            if byte_count > limits.max_bytes:
                raise InputLimitError(
                    source_name,
                    "XML bytes",
                    byte_count,
                    limits.max_bytes,
                )
            parser.Parse(raw, False)
        parser.Parse(b"", True)
    except (InputLimitError, BoundedXmlError):
        raise
    except expat.ExpatError as exc:
        raise BoundedXmlError(f"{source_name}: invalid or unsafe XML: {exc}") from exc

    if root is None:
        raise BoundedXmlError(f"{source_name}: XML document is empty")
    if stack:
        raise BoundedXmlError(f"{source_name}: XML document ended before all elements closed")
    return root


def _positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
