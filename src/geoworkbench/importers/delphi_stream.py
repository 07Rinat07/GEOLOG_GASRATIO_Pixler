from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from io import BytesIO
import math
import re
import struct
from typing import Any, BinaryIO


class DelphiStreamError(ValueError):
    """Raised when a Delphi component stream cannot be decoded safely."""


class DelphiValueType(IntEnum):
    NULL = 0
    LIST = 1
    INT8 = 2
    INT16 = 3
    INT32 = 4
    EXTENDED = 5
    STRING = 6
    IDENT = 7
    FALSE = 8
    TRUE = 9
    BINARY = 10
    SET = 11
    LSTRING = 12
    NIL = 13
    COLLECTION = 14
    SINGLE = 15
    CURRENCY = 16
    DATE = 17
    WSTRING = 18
    INT64 = 19
    UTF8STRING = 20
    DOUBLE = 21


@dataclass(frozen=True, slots=True)
class DelphiBinary:
    payload: bytes


@dataclass(frozen=True, slots=True)
class DelphiSet:
    values: tuple[str, ...]


@dataclass(slots=True)
class DelphiComponent:
    class_name: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    children: list["DelphiComponent"] = field(default_factory=list)
    inherited: bool = False
    inline: bool = False
    child_position: int | None = None

    def walk(self) -> list["DelphiComponent"]:
        result = [self]
        for child in self.children:
            result.extend(child.walk())
        return result


@dataclass(frozen=True, slots=True)
class DelphiComponentStream:
    root: DelphiComponent
    signature_offset: int
    source_kind: str = "binary"


class DelphiBinaryReader:
    SIGNATURE = b"TPF0"
    MAX_STREAM_BYTES = 64 * 1024 * 1024
    MAX_BINARY_BYTES = 16 * 1024 * 1024
    MAX_STRING_BYTES = 4 * 1024 * 1024
    MAX_COMPONENTS = 20_000
    MAX_DEPTH = 128
    PREFIX_MASK = 0xF0
    PREFIX_INHERITED = 0x01
    PREFIX_CHILD_POS = 0x02
    PREFIX_INLINE = 0x04

    def __init__(self, payload: bytes, *, encoding: str | None = None) -> None:
        if len(payload) > self.MAX_STREAM_BYTES:
            raise DelphiStreamError("SKF/Delphi stream exceeds the 64 MB safety limit")
        offset = payload.find(self.SIGNATURE)
        if offset < 0:
            raise DelphiStreamError("Delphi component-stream signature TPF0 was not found")
        self._stream: BinaryIO = BytesIO(payload[offset + len(self.SIGNATURE) :])
        self.signature_offset = offset
        self._encoding = encoding
        self._component_count = 0

    def parse(self) -> DelphiComponentStream:
        root = self._read_component(0)
        if root is None:
            raise DelphiStreamError("Delphi stream does not contain a root component")
        return DelphiComponentStream(root, self.signature_offset)

    def _read_component(self, depth: int) -> DelphiComponent | None:
        if depth > self.MAX_DEPTH:
            raise DelphiStreamError("Delphi component nesting is too deep")
        inherited, inline, child_position = self._read_prefix()
        class_name = self._read_short_string()
        if not class_name:
            return None
        name = self._read_short_string()
        self._component_count += 1
        if self._component_count > self.MAX_COMPONENTS:
            raise DelphiStreamError("Delphi stream contains too many components")
        properties: dict[str, Any] = {}
        while True:
            property_name = self._read_short_string()
            if not property_name:
                break
            properties[property_name] = self._read_typed_value()
        children: list[DelphiComponent] = []
        while True:
            position = self._stream.tell()
            child = self._read_component(depth + 1)
            if child is None:
                break
            if self._stream.tell() <= position:
                raise DelphiStreamError("Delphi component parser did not advance")
            children.append(child)
        return DelphiComponent(
            class_name=class_name,
            name=name,
            properties=properties,
            children=children,
            inherited=inherited,
            inline=inline,
            child_position=child_position,
        )

    def _read_prefix(self) -> tuple[bool, bool, int | None]:
        marker = self._peek_byte()
        if marker is None or marker & self.PREFIX_MASK != self.PREFIX_MASK:
            return False, False, None
        prefix = self._read_u8()
        child_position = self._read_integer() if prefix & self.PREFIX_CHILD_POS else None
        return (
            bool(prefix & self.PREFIX_INHERITED),
            bool(prefix & self.PREFIX_INLINE),
            child_position,
        )

    def _read_typed_value(self) -> Any:
        raw_type = self._read_u8()
        try:
            value_type = DelphiValueType(raw_type)
        except ValueError as exc:
            raise DelphiStreamError(f"Unsupported Delphi value type: {raw_type}") from exc
        if value_type is DelphiValueType.NULL:
            return None
        if value_type is DelphiValueType.LIST:
            values: list[Any] = []
            while self._peek_byte() != DelphiValueType.NULL:
                values.append(self._read_typed_value())
            self._expect_null()
            return values
        if value_type is DelphiValueType.INT8:
            return self._read_struct("<b")
        if value_type is DelphiValueType.INT16:
            return self._read_struct("<h")
        if value_type is DelphiValueType.INT32:
            return self._read_struct("<i")
        if value_type is DelphiValueType.EXTENDED:
            return _extended80_to_float(self._read_exact(10))
        if value_type in {DelphiValueType.STRING, DelphiValueType.IDENT}:
            return self._read_short_string()
        if value_type is DelphiValueType.FALSE:
            return False
        if value_type is DelphiValueType.TRUE:
            return True
        if value_type is DelphiValueType.BINARY:
            size = self._read_i32_size(self.MAX_BINARY_BYTES, "binary property")
            return DelphiBinary(self._read_exact(size))
        if value_type is DelphiValueType.SET:
            set_values: list[str] = []
            while True:
                value = self._read_short_string()
                if not value:
                    return DelphiSet(tuple(set_values))
                set_values.append(value)
        if value_type is DelphiValueType.LSTRING:
            size = self._read_i32_size(self.MAX_STRING_BYTES, "long string")
            return self._decode(self._read_exact(size))
        if value_type is DelphiValueType.NIL:
            return None
        if value_type is DelphiValueType.COLLECTION:
            return self._read_collection()
        if value_type is DelphiValueType.SINGLE:
            return self._read_struct("<f")
        if value_type is DelphiValueType.CURRENCY:
            return self._read_struct("<q") / 10_000.0
        if value_type is DelphiValueType.DATE:
            return self._read_struct("<d")
        if value_type is DelphiValueType.WSTRING:
            char_count = self._read_i32_size(self.MAX_STRING_BYTES // 2, "wide string")
            return self._read_exact(char_count * 2).decode("utf-16-le", errors="replace")
        if value_type is DelphiValueType.INT64:
            return self._read_struct("<q")
        if value_type is DelphiValueType.UTF8STRING:
            size = self._read_i32_size(self.MAX_STRING_BYTES, "UTF-8 string")
            return self._read_exact(size).decode("utf-8", errors="replace")
        if value_type is DelphiValueType.DOUBLE:
            return self._read_struct("<d")
        raise DelphiStreamError(f"Unhandled Delphi value type: {value_type.name}")

    def _read_collection(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        integer_types = {
            DelphiValueType.INT8,
            DelphiValueType.INT16,
            DelphiValueType.INT32,
            DelphiValueType.INT64,
        }
        while True:
            marker = self._peek_byte()
            if marker == DelphiValueType.NULL:
                self._expect_null()
                return items
            item: dict[str, Any] = {}
            if marker in integer_types:
                item["__index__"] = self._read_typed_value()
                marker = self._peek_byte()
            if marker != DelphiValueType.LIST:
                raise DelphiStreamError("Collection item must start with vaList")
            self._read_u8()
            while self._peek_byte() != DelphiValueType.NULL:
                name = self._read_short_string()
                if not name:
                    raise DelphiStreamError("Unexpected empty collection property name")
                item[name] = self._read_typed_value()
            self._expect_null()
            items.append(item)

    def _read_integer(self) -> int:
        raw_type = self._read_u8()
        if raw_type == DelphiValueType.INT8:
            return int(self._read_struct("<b"))
        if raw_type == DelphiValueType.INT16:
            return int(self._read_struct("<h"))
        if raw_type == DelphiValueType.INT32:
            return int(self._read_struct("<i"))
        if raw_type == DelphiValueType.INT64:
            return int(self._read_struct("<q"))
        raise DelphiStreamError("Integer content expected in Delphi stream")

    def _read_short_string(self) -> str:
        size = self._read_u8()
        return self._decode(self._read_exact(size)) if size else ""

    def _decode(self, payload: bytes) -> str:
        if not payload:
            return ""
        if self._encoding:
            return payload.decode(self._encoding, errors="replace")
        candidates: list[tuple[float, str]] = []
        for encoding in ("utf-8", "cp1251", "cp866", "latin-1"):
            try:
                text = payload.decode(encoding)
            except UnicodeDecodeError:
                continue
            control_count = sum(ord(char) < 32 and char not in "\t\r\n" for char in text)
            replacement_count = text.count("\ufffd")
            cyrillic_count = sum("А" <= char <= "я" or char in "Ёё" for char in text)
            printable_count = sum(char.isprintable() for char in text)
            score = printable_count + cyrillic_count * 2 - control_count * 10 - replacement_count * 20
            if encoding == "utf-8":
                score += 1
            candidates.append((score, text))
        return max(candidates, key=lambda item: item[0])[1] if candidates else payload.hex()

    def _read_i32_size(self, limit: int, label: str) -> int:
        size = int(self._read_struct("<i"))
        if size < 0 or size > limit:
            raise DelphiStreamError(f"Invalid {label} size: {size}")
        return size

    def _expect_null(self) -> None:
        if self._read_u8() != DelphiValueType.NULL:
            raise DelphiStreamError("Expected vaNull list terminator")

    def _peek_byte(self) -> int | None:
        position = self._stream.tell()
        value = self._stream.read(1)
        self._stream.seek(position)
        return value[0] if value else None

    def _read_u8(self) -> int:
        return self._read_exact(1)[0]

    def _read_struct(self, fmt: str) -> Any:
        size = struct.calcsize(fmt)
        return struct.unpack(fmt, self._read_exact(size))[0]

    def _read_exact(self, size: int) -> bytes:
        payload = self._stream.read(size)
        if len(payload) != size:
            raise DelphiStreamError("Unexpected end of Delphi component stream")
        return payload


def parse_delphi_component_stream(payload: bytes, *, encoding: str | None = None) -> DelphiComponentStream:
    """Parse a binary Delphi component stream embedded in an SKF file.

    The importer never instantiates Delphi classes or executes event handlers. It
    decodes the filer stream into a neutral tree that is safe to inspect and map
    into the application's own form/header models.
    """

    return DelphiBinaryReader(payload, encoding=encoding).parse()


def _extended80_to_float(payload: bytes) -> float:
    if len(payload) != 10:
        raise DelphiStreamError("Delphi Extended value must contain 10 bytes")
    significand = int.from_bytes(payload[:8], "little", signed=False)
    exponent_sign = int.from_bytes(payload[8:], "little", signed=False)
    sign = -1.0 if exponent_sign & 0x8000 else 1.0
    exponent = exponent_sign & 0x7FFF
    if exponent == 0 and significand == 0:
        return math.copysign(0.0, sign)
    if exponent == 0x7FFF:
        return math.copysign(math.inf, sign) if significand == 0x8000000000000000 else math.nan
    integer_bit = (significand >> 63) & 1
    fraction = significand & ((1 << 63) - 1)
    mantissa = integer_bit + fraction / float(1 << 63)
    return sign * math.ldexp(mantissa, exponent - 16383)


def normalized_property_map(component: DelphiComponent) -> dict[str, Any]:
    return {_normalize_key(key): value for key, value in component.properties.items()}


def get_property(component: DelphiComponent, *names: str, default: Any = None) -> Any:
    properties = normalized_property_map(component)
    for name in names:
        value = properties.get(_normalize_key(name))
        if value is not None:
            return value
    return default


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9а-я]+", "", value.casefold())
