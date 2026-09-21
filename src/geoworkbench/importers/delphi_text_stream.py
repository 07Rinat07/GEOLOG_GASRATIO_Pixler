from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from geoworkbench.importers.delphi_stream import (
    DelphiBinary,
    DelphiBinaryReader,
    DelphiComponent,
    DelphiComponentStream,
    DelphiSet,
    DelphiStreamError,
)


_COMPONENT_HEADER = re.compile(
    r"^(?P<kind>object|inherited|inline)\s+"
    r"(?:(?P<name>[^:\s]+)\s*:\s*)?"
    r"(?P<class>[A-Za-z_]\w*)\s*$",
    re.IGNORECASE,
)
_PROPERTY = re.compile(
    r"^(?P<name>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*=\s*(?P<value>.*)$"
)
_ACTIVE_PAGE = re.compile(r"^\s*ActivePage\s*=\s*(?P<value>\d+)\s*$", re.IGNORECASE)
_PAGE_NAME = re.compile(r"^\s*Name(?P<index>\d+)\s*=\s*(?P<value>.*)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DelphiTextDocument:
    """Neutral representation of one textual Delphi DFM/GeoSight document."""

    components: tuple[DelphiComponent, ...]
    encoding: str
    active_page: int | None = None
    page_names: tuple[tuple[int, str], ...] = ()

    def page_name(self, index: int) -> str:
        for page_index, name in self.page_names:
            if page_index == index:
                return name
        return ""

    def streams(self) -> tuple[DelphiComponentStream, ...]:
        return tuple(
            DelphiComponentStream(root, 0, source_kind="text")
            for root in self.components
        )


def decode_delphi_text(
    payload: bytes,
    *,
    encoding: str | None = None,
) -> tuple[str, str]:
    """Decode a textual Delphi stream without locale-dependent defaults."""

    if len(payload) > DelphiBinaryReader.MAX_STREAM_BYTES:
        raise DelphiStreamError("Delphi text stream exceeds the 64 MB safety limit")
    if encoding:
        try:
            return payload.decode(encoding), encoding
        except (LookupError, UnicodeDecodeError) as exc:
            raise DelphiStreamError(
                f"Cannot decode Delphi text stream as {encoding}"
            ) from exc

    candidates: tuple[tuple[str, bytes | None], ...] = (
        ("utf-8-sig", b"\xef\xbb\xbf"),
        ("utf-16", b"\xff\xfe"),
        ("utf-16", b"\xfe\xff"),
        ("utf-8", None),
        ("cp1251", None),
    )
    for candidate, required_prefix in candidates:
        if required_prefix is not None and not payload.startswith(required_prefix):
            continue
        try:
            text = payload.decode(candidate)
        except UnicodeDecodeError:
            continue
        if "\x00" in text[:4096] and not candidate.startswith("utf-16"):
            continue
        return text, candidate
    raise DelphiStreamError("Delphi text stream encoding is not recognized")


def parse_delphi_text_component_stream(
    payload: bytes,
    *,
    encoding: str | None = None,
) -> DelphiTextDocument:
    """Parse textual Delphi DFM syntax into the same neutral tree as TPF0.

    GeoSight .sf2/.sd2/.gsf/.gs2 files use Delphi textual component
    serialization, sometimes wrapped by [Desktop]/[0] sections. Unknown
    properties remain inert values; no Delphi class or event handler executes.
    """

    text, resolved_encoding = decode_delphi_text(payload, encoding=encoding)
    parser = _DelphiTextParser(text)
    components = parser.parse_components()
    if not components:
        raise DelphiStreamError("Delphi text stream does not contain an object component")

    active_page: int | None = None
    names: dict[int, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        active_match = _ACTIVE_PAGE.match(line)
        if active_match is not None:
            active_page = int(active_match.group("value"))
            continue
        name_match = _PAGE_NAME.match(line)
        if name_match is not None:
            names[int(name_match.group("index"))] = name_match.group("value").strip()

    if active_page is not None and not 0 <= active_page < len(components):
        active_page = None
    return DelphiTextDocument(
        components=components,
        encoding=resolved_encoding,
        active_page=active_page,
        page_names=tuple(sorted(names.items())),
    )


class _DelphiTextParser:
    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()
        self._index = 0
        self._component_count = 0

    def parse_components(self) -> tuple[DelphiComponent, ...]:
        roots: list[DelphiComponent] = []
        while self._index < len(self._lines):
            line = self._current()
            if _COMPONENT_HEADER.match(line):
                roots.append(self._read_component(0))
            else:
                self._index += 1
        return tuple(roots)

    def _read_component(self, depth: int) -> DelphiComponent:
        if depth > DelphiBinaryReader.MAX_DEPTH:
            raise DelphiStreamError("Delphi component nesting is too deep")
        header = _COMPONENT_HEADER.match(self._current())
        if header is None:
            raise DelphiStreamError("Delphi component header expected")
        kind = header.group("kind").casefold()
        component = DelphiComponent(
            class_name=header.group("class"),
            name=header.group("name") or "",
            inherited=kind == "inherited",
            inline=kind == "inline",
        )
        self._component_count += 1
        if self._component_count > DelphiBinaryReader.MAX_COMPONENTS:
            raise DelphiStreamError("Delphi stream contains too many components")
        self._index += 1

        while self._index < len(self._lines):
            line = self._current()
            if line == "end":
                self._index += 1
                return component
            if line == "end>":
                self._lines[self._index] = ">"
                return component
            if _COMPONENT_HEADER.match(line):
                component.children.append(self._read_component(depth + 1))
                continue
            match = _PROPERTY.match(line)
            if match is None:
                self._index += 1
                continue
            component.properties[match.group("name")] = self._read_value(
                match.group("value").strip(),
                depth=depth + 1,
            )
        return component

    def _read_value(self, raw: str, *, depth: int) -> Any:
        if raw == "<":
            return self._read_collection(depth)
        if raw == "(":
            return self._read_list()
        if raw == "{":
            return self._read_binary()
        self._index += 1
        return _parse_scalar(raw)

    def _read_collection(self, depth: int) -> list[dict[str, Any]]:
        if depth > DelphiBinaryReader.MAX_DEPTH:
            raise DelphiStreamError("Delphi collection nesting is too deep")
        self._index += 1
        items: list[dict[str, Any]] = []
        while self._index < len(self._lines):
            line = self._current()
            if line == ">":
                self._index += 1
                return items
            if line == "item":
                self._index += 1
                items.append(self._read_collection_item(depth + 1))
                continue
            self._index += 1
        raise DelphiStreamError("Unterminated Delphi collection")

    def _read_collection_item(self, depth: int) -> dict[str, Any]:
        item: dict[str, Any] = {}
        embedded_components: list[DelphiComponent] = []
        while self._index < len(self._lines):
            line = self._current()
            if line == "end":
                self._index += 1
                if embedded_components:
                    item["__components__"] = embedded_components
                return item
            if line == "end>":
                self._lines[self._index] = ">"
                if embedded_components:
                    item["__components__"] = embedded_components
                return item
            if _COMPONENT_HEADER.match(line):
                embedded_components.append(self._read_component(depth + 1))
                continue
            match = _PROPERTY.match(line)
            if match is None:
                self._index += 1
                continue
            item[match.group("name")] = self._read_value(
                match.group("value").strip(),
                depth=depth + 1,
            )
        raise DelphiStreamError("Unterminated Delphi collection item")

    def _read_list(self) -> list[Any]:
        self._index += 1
        values: list[Any] = []
        while self._index < len(self._lines):
            line = self._current()
            if line == ")":
                self._index += 1
                return values
            if line.endswith(")"):
                prefix = line[:-1].strip().rstrip(",")
                if prefix:
                    values.append(_parse_scalar(prefix))
                self._index += 1
                return values
            candidate = line.rstrip(",")
            if candidate:
                values.append(_parse_scalar(candidate))
            self._index += 1
        raise DelphiStreamError("Unterminated Delphi list")

    def _read_binary(self) -> DelphiBinary:
        self._index += 1
        chunks: list[str] = []
        while self._index < len(self._lines):
            line = self._current()
            if line == "}":
                self._index += 1
                break
            if line.endswith("}"):
                chunks.append(line[:-1].strip())
                self._index += 1
                break
            chunks.append(line)
            self._index += 1
        else:
            raise DelphiStreamError("Unterminated Delphi binary property")

        encoded = "".join(chunks)
        if len(encoded) > DelphiBinaryReader.MAX_BINARY_BYTES * 2:
            raise DelphiStreamError("Delphi binary property exceeds the safety limit")
        if not re.fullmatch(r"[0-9A-Fa-f\s]*", encoded):
            raise DelphiStreamError("Delphi binary property contains non-hex data")
        try:
            payload = bytes.fromhex(encoded)
        except ValueError as exc:
            raise DelphiStreamError("Delphi binary property contains invalid hex") from exc
        return DelphiBinary(payload)

    def _current(self) -> str:
        return self._lines[self._index].strip().lstrip("\ufeff")


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    lowered = value.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "nil":
        return None
    if value.startswith("'") or value.startswith("#"):
        return _parse_pascal_string(value)
    if value.startswith("$"):
        try:
            return int(value[1:], 16)
        except ValueError:
            return value
    if value.startswith("[") and value.endswith("]"):
        entries = tuple(
            item.strip()
            for item in value[1:-1].split(",")
            if item.strip()
        )
        return DelphiSet(entries)
    if re.fullmatch(r"[+-]?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    if re.fullmatch(
        r"[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?",
        value,
    ):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _parse_pascal_string(raw: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char.isspace() or char == "+":
            index += 1
            continue
        if char == "'":
            index += 1
            chunk: list[str] = []
            while index < len(raw):
                if raw[index] != "'":
                    chunk.append(raw[index])
                    index += 1
                    continue
                if index + 1 < len(raw) and raw[index + 1] == "'":
                    chunk.append("'")
                    index += 2
                    continue
                index += 1
                break
            result.append("".join(chunk))
            continue
        if char == "#":
            index += 1
            end = index
            while end < len(raw) and raw[end].isdigit():
                end += 1
            if end == index:
                return raw
            codepoint = int(raw[index:end])
            if 0 <= codepoint <= 0x10FFFF:
                result.append(chr(codepoint))
            index = end
            continue
        return raw
    return "".join(result)


__all__ = [
    "DelphiTextDocument",
    "decode_delphi_text",
    "parse_delphi_text_component_stream",
]
