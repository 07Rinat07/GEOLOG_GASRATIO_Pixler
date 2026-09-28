from __future__ import annotations

import base64
import binascii
import json
import math
import re
import zlib
from dataclasses import dataclass
from typing import Any


GEOLOGY_METADATA_SCHEMA = 1
_MARKER = b"GEOWORKBENCH_GEOLOGY_METADATA"
_PAYLOAD_PREFIX = b"# GEOLOGY_ZLIB_BASE64="
_PAYLOAD_CONT_PREFIX = b"# GEOLOGY_ZLIB_BASE64_CONT="
_MAX_COMPRESSED_BYTES = 2 * 1024 * 1024
_MAX_ENCODED_BYTES = ((_MAX_COMPRESSED_BYTES + 2) // 3) * 4
_MAX_DECOMPRESSED_BYTES = 8 * 1024 * 1024
_MAX_DESCRIPTIONS = 100_000
_MAX_STRATIGRAPHY = 10_000
_MAX_TEXT = 4_000
_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
_MAX_LEGACY_HEADER_BYTES = 8 * 1024 * 1024
_LEGACY_STRAT_PREFIX = "# STRAT "
_LEGACY_DESC_PREFIX = "# DESC "
_LEGACY_SOURCE_PREFIX = "# GEOLOGY_SOURCE="


@dataclass(frozen=True, slots=True)
class LasGeologyDescription:
    description_id: int
    top_depth: float
    bottom_depth: float
    text_ru: str


@dataclass(frozen=True, slots=True)
class LasStratigraphyEntry:
    top_depth: float
    bottom_depth: float
    code: str
    name_ru: str
    rank: str | None = None
    color: str | None = None
    description_ru: str | None = None


@dataclass(frozen=True, slots=True)
class LasGeologyMetadata:
    source: str
    descriptions: dict[int, LasGeologyDescription]
    stratigraphy: tuple[LasStratigraphyEntry, ...]
    lba_type_codes: dict[int, str]
    lba_color_codes: dict[int, str]
    schema_version: int = GEOLOGY_METADATA_SCHEMA

    def description(self, description_id: int | None) -> str | None:
        if description_id is None:
            return None
        item = self.descriptions.get(description_id)
        return item.text_ru if item is not None else None

    def lba_type(self, code: int | None) -> str | None:
        return self.lba_type_codes.get(code) if code is not None else None

    def lba_color(self, code: int | None) -> str | None:
        return self.lba_color_codes.get(code) if code is not None else None


def geology_metadata_from_las_bytes(raw: bytes) -> LasGeologyMetadata | None:
    """Read portable geology metadata without making LAS import fragile.

    The current bounded zlib/JSON contract is preferred. Older DIGITAL GEOLOG
    field LAS files used bounded plain-text # STRAT / # DESC records in ~Other;
    that contract remains readable for backward compatibility. Invalid optional
    metadata is ignored deliberately so the base LAS can still open.
    """

    if not isinstance(raw, bytes):
        return None

    current = _current_metadata_from_las_bytes(raw)
    if current is not None:
        return current
    return _legacy_metadata_from_las_bytes(raw)


def _current_metadata_from_las_bytes(raw: bytes) -> LasGeologyMetadata | None:
    if _MARKER not in raw:
        return None
    section_matches = list(re.finditer(rb"(?m)^[ \t]*~[^\r\n]*", raw))
    for index in range(len(section_matches) - 1, -1, -1):
        start = section_matches[index].start()
        end = (
            section_matches[index + 1].start()
            if index + 1 < len(section_matches)
            else len(raw)
        )
        section = raw[start:end]
        if _MARKER not in section:
            continue
        try:
            encoded = _payload_from_section(section)
            if encoded is None:
                continue
            if len(encoded) > _MAX_ENCODED_BYTES:
                continue
            compressed = base64.b64decode(encoded, validate=True)
            if len(compressed) > _MAX_COMPRESSED_BYTES:
                continue
            payload = _decompress_bounded(compressed)
            decoded = json.loads(payload.decode("utf-8"))
            return _metadata_from_dict(decoded)
        except (
            binascii.Error,
            UnicodeDecodeError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
            RecursionError,
            zlib.error,
        ):
            continue
    return None


def _legacy_metadata_from_las_bytes(raw: bytes) -> LasGeologyMetadata | None:
    """Parse the bounded pre-ASCII legacy geology annotation contract."""

    ascii_offsets = [
        offset
        for marker in (b"~ASCII", b"~Ascii", b"~ascii")
        if (offset := raw.find(marker)) >= 0
    ]
    header_end = min(ascii_offsets) if ascii_offsets else min(len(raw), _MAX_LEGACY_HEADER_BYTES)
    if header_end > _MAX_LEGACY_HEADER_BYTES:
        return None
    header = raw[:header_end]
    if b"# STRAT " not in header and b"# DESC " not in header:
        return None

    text: str | None = None
    for encoding in ("utf-8", "cp1251"):
        try:
            text = header.decode(encoding, errors="strict")
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return None

    source = "legacy DIGITAL GEOLOG LAS geology metadata"
    descriptions: dict[str, dict[str, object]] = {}
    stratigraphy: list[dict[str, object]] = []
    try:
        for line in text.splitlines():
            if line.startswith(_LEGACY_SOURCE_PREFIX):
                candidate = line.removeprefix(_LEGACY_SOURCE_PREFIX).strip()
                if candidate:
                    source = _bounded_text(candidate, "source", maximum=500)
                continue
            if line.startswith(_LEGACY_DESC_PREFIX):
                if len(descriptions) >= _MAX_DESCRIPTIONS:
                    raise ValueError("Too many legacy geology descriptions")
                match = re.fullmatch(
                    r"# DESC id=(\d+); top=([^;]+); bottom=([^;]+); text=(.*)",
                    line,
                )
                if match is None:
                    raise ValueError("Invalid legacy geology description")
                description_id, top, bottom, description = match.groups()
                descriptions[description_id] = {
                    "top": top.strip(),
                    "bottom": bottom.strip(),
                    "text_ru": description.strip(),
                }
                continue
            if line.startswith(_LEGACY_STRAT_PREFIX):
                if len(stratigraphy) >= _MAX_STRATIGRAPHY:
                    raise ValueError("Too many legacy stratigraphy intervals")
                match = re.fullmatch(
                    r"# STRAT id=\d+; top=([^;]+); bottom=([^;]+); "
                    r"code=([^;]+); rank=([^;]+); name=(.*)",
                    line,
                )
                if match is None:
                    raise ValueError("Invalid legacy stratigraphy interval")
                top, bottom, code, rank, name = match.groups()
                stratigraphy.append(
                    {
                        "top": top.strip(),
                        "bottom": bottom.strip(),
                        "code": code.strip(),
                        "rank": rank.strip(),
                        "name_ru": name.strip(),
                    }
                )
        if not descriptions and not stratigraphy:
            return None
        return LasGeologyMetadata(
            source=source,
            descriptions=_descriptions_from_raw(descriptions),
            stratigraphy=_stratigraphy_from_raw(stratigraphy),
            lba_type_codes={},
            lba_color_codes={},
        )
    except (TypeError, ValueError, RecursionError):
        return None


def _payload_from_section(section: bytes) -> str | None:
    chunks: list[str] = []
    encoded_size = 0
    for line in section.splitlines():
        payload: bytes | None = None
        if line.startswith(_PAYLOAD_PREFIX):
            chunks = []
            encoded_size = 0
            payload = line.removeprefix(_PAYLOAD_PREFIX)
        elif chunks and line.startswith(_PAYLOAD_CONT_PREFIX):
            payload = line.removeprefix(_PAYLOAD_CONT_PREFIX)
        if payload is None:
            continue
        encoded_size += len(payload)
        if encoded_size > _MAX_ENCODED_BYTES:
            raise ValueError("Embedded geology metadata exceeds the safe encoded size limit")
        chunks.append(payload.decode("ascii", errors="strict"))
    return "".join(chunks) if chunks else None


def _decompress_bounded(compressed: bytes) -> bytes:
    decompressor = zlib.decompressobj()
    payload = decompressor.decompress(
        compressed,
        _MAX_DECOMPRESSED_BYTES + 1,
    )
    if len(payload) > _MAX_DECOMPRESSED_BYTES or decompressor.unconsumed_tail:
        raise ValueError("Embedded geology metadata exceeds the safe size limit")
    payload += decompressor.flush()
    if len(payload) > _MAX_DECOMPRESSED_BYTES:
        raise ValueError("Embedded geology metadata exceeds the safe size limit")
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError("Embedded geology metadata is not one complete zlib stream")
    return payload


def _metadata_from_dict(raw: Any) -> LasGeologyMetadata:
    if not isinstance(raw, dict):
        raise ValueError("Geology metadata must be a JSON object")
    if raw.get("schema_version") != GEOLOGY_METADATA_SCHEMA:
        raise ValueError("Unsupported geology metadata schema")

    source = _bounded_text(raw.get("source"), "source", maximum=500)
    descriptions = _descriptions_from_raw(raw.get("descriptions", {}))
    stratigraphy = _stratigraphy_from_raw(raw.get("stratigraphy", []))
    type_codes = _code_dictionary(raw.get("lba_type_codes", {}), "lba_type_codes")
    color_codes = _code_dictionary(
        raw.get("lba_color_codes", {}),
        "lba_color_codes",
    )
    return LasGeologyMetadata(
        source=source,
        descriptions=descriptions,
        stratigraphy=stratigraphy,
        lba_type_codes=type_codes,
        lba_color_codes=color_codes,
    )


def _descriptions_from_raw(raw: Any) -> dict[int, LasGeologyDescription]:
    if not isinstance(raw, dict) or len(raw) > _MAX_DESCRIPTIONS:
        raise ValueError("Invalid geology descriptions map")
    result: dict[int, LasGeologyDescription] = {}
    for key, value in raw.items():
        try:
            description_id = int(key)
        except (TypeError, ValueError) as exc:
            raise ValueError("Description ID must be an integer") from exc
        if description_id < 1 or not isinstance(value, dict):
            raise ValueError("Invalid geology description entry")
        top = _finite_depth(value.get("top"), "description.top")
        bottom = _finite_depth(value.get("bottom"), "description.bottom")
        if bottom <= top:
            raise ValueError("Description interval must have bottom > top")
        text_ru = _bounded_text(value.get("text_ru"), "description.text_ru")
        result[description_id] = LasGeologyDescription(
            description_id,
            top,
            bottom,
            text_ru,
        )
    return result


def _stratigraphy_from_raw(raw: Any) -> tuple[LasStratigraphyEntry, ...]:
    if not isinstance(raw, list) or len(raw) > _MAX_STRATIGRAPHY:
        raise ValueError("Invalid stratigraphy metadata")
    result: list[LasStratigraphyEntry] = []
    for value in raw:
        if not isinstance(value, dict):
            raise ValueError("Invalid stratigraphy entry")
        top = _finite_depth(value.get("top"), "stratigraphy.top")
        bottom = _finite_depth(value.get("bottom"), "stratigraphy.bottom")
        if bottom <= top:
            raise ValueError("Stratigraphy interval must have bottom > top")
        code = _bounded_text(
            value.get("short") or value.get("code"),
            "stratigraphy.code",
            maximum=80,
        )
        name_ru = _bounded_text(
            value.get("name_ru"),
            "stratigraphy.name_ru",
            maximum=300,
        )
        rank = _optional_text(value.get("rank"), maximum=80)
        color = _optional_text(value.get("color"), maximum=7)
        if color is not None and not _COLOR_PATTERN.fullmatch(color):
            raise ValueError("Invalid stratigraphy color")
        description_ru = _optional_text(
            value.get("description_ru"),
            maximum=_MAX_TEXT,
        )
        result.append(
            LasStratigraphyEntry(
                top_depth=top,
                bottom_depth=bottom,
                code=code,
                name_ru=name_ru,
                rank=rank,
                color=color.lower() if color is not None else None,
                description_ru=description_ru,
            )
        )
    result.sort(key=lambda item: (item.top_depth, item.bottom_depth, item.code))
    previous_by_rank: dict[str, LasStratigraphyEntry] = {}
    for item in result:
        rank_key = (item.rank or "").strip().casefold()
        previous = previous_by_rank.get(rank_key)
        if previous is not None and item.top_depth < previous.bottom_depth:
            raise ValueError("Overlapping stratigraphy intervals of the same rank")
        previous_by_rank[rank_key] = item
    return tuple(result)


def _code_dictionary(raw: Any, label: str) -> dict[int, str]:
    if not isinstance(raw, dict) or len(raw) > 1_000:
        raise ValueError(f"Invalid {label}")
    result: dict[int, str] = {}
    for key, value in raw.items():
        try:
            code = int(key)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} key must be an integer") from exc
        if not 1 <= code <= 999_999:
            raise ValueError(f"{label} key is outside the supported range")
        result[code] = _bounded_text(value, label, maximum=80)
    return result


def _finite_depth(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{label} must be finite")
    return parsed


def _bounded_text(value: Any, label: str, *, maximum: int = _MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    text = value.strip()
    if not text or len(text) > maximum:
        raise ValueError(f"{label} is empty or too long")
    return text


def _optional_text(value: Any, *, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional metadata text must be a string")
    text = value.strip()
    if not text:
        return None
    if len(text) > maximum:
        raise ValueError("Optional metadata text is too long")
    return text
