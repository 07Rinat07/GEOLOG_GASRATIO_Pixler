from __future__ import annotations

import base64
import binascii
import json
import math
from pathlib import Path
import re
import zlib
from dataclasses import dataclass
from typing import Any

from geoworkbench.domain.models import Well
from geoworkbench.services.lba_standard import (
    LBA_STANDARD_GROUPS,
    lba_color_code,
)


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
class LasGeologyExportPlan:
    """One deterministic contract shared by LAS curves and portable metadata."""

    metadata: "LasGeologyMetadata"
    description_ids: dict[str, int]
    lithology_description_ids: dict[str, int]
    stratigraphy_codes: dict[str, int]
    lba_type_codes: dict[str, int]
    lba_color_codes: dict[str, int]


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
    """Read optional portable geology metadata without making LAS import fragile.

    Invalid/malformed metadata is ignored deliberately.  The raw LAS remains the
    source of truth and must still be readable when this optional annotation is
    absent or damaged.
    """

    if not isinstance(raw, bytes) or _MARKER not in raw:
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



def geology_export_plan_from_well(well: Well) -> LasGeologyExportPlan:
    """Build stable numeric carriers plus portable text dictionaries for one well."""

    description_ids: dict[str, int] = {}
    lithology_description_ids: dict[str, int] = {}
    descriptions: dict[int, LasGeologyDescription] = {}
    next_description_id = 1

    for interval in sorted(
        well.lithology,
        key=lambda item: (
            float(item.top_depth),
            float(item.bottom_depth),
            item.interval_id,
        ),
    ):
        text = (
            interval.description_i18n.get("ru")
            or interval.description
            or ""
        ).strip()
        if not text:
            continue
        lithology_description_ids[interval.interval_id] = next_description_id
        descriptions[next_description_id] = LasGeologyDescription(
            next_description_id,
            float(interval.top_depth),
            float(interval.bottom_depth),
            text,
        )
        next_description_id += 1

    for sample in sorted(
        well.cuttings,
        key=lambda item: (float(item.top_depth), float(item.bottom_depth), item.sample_id),
    ):
        text = (
            sample.description_i18n.get("ru")
            or sample.description
            or ""
        ).strip()
        if not text:
            continue
        description_ids[sample.sample_id] = next_description_id
        descriptions[next_description_id] = LasGeologyDescription(
            next_description_id,
            float(sample.top_depth),
            float(sample.bottom_depth),
            text,
        )
        next_description_id += 1

    stratigraphy_codes: dict[str, int] = {}
    stratigraphy: list[LasStratigraphyEntry] = []
    for numeric_code, interval in enumerate(
        sorted(
            well.stratigraphy,
            key=lambda item: (
                float(item.top_depth),
                float(item.bottom_depth),
                item.code,
                item.interval_id,
            ),
        ),
        start=1,
    ):
        stratigraphy_codes[interval.interval_id] = numeric_code
        name_ru = (
            interval.name_i18n.get("ru")
            or interval.name
            or interval.code
            or str(numeric_code)
        ).strip()
        description_ru = (
            interval.description_i18n.get("ru")
            or interval.description
            or None
        )
        stratigraphy.append(
            LasStratigraphyEntry(
                top_depth=float(interval.top_depth),
                bottom_depth=float(interval.bottom_depth),
                code=(interval.code or str(numeric_code)).strip(),
                name_ru=name_ru,
                rank=(interval.rank or None),
                color=(interval.color or "#dbeafe").lower(),
                description_ru=(
                    description_ru.strip()
                    if isinstance(description_ru, str) and description_ru.strip()
                    else None
                ),
            )
        )

    # Standard type codes deliberately match the field LAS convention 1..5.
    lba_type_codes = {
        standard.type_id: standard.group
        for standard in LBA_STANDARD_GROUPS
    }
    metadata_type_codes = {
        standard.group: standard.code
        for standard in LBA_STANDARD_GROUPS
    }

    color_labels = sorted(
        {
            lba_color_code(sample.lba_color)
            for sample in well.cuttings
            if lba_color_code(sample.lba_color)
        }
    )
    lba_color_codes = {
        label: index
        for index, label in enumerate(color_labels, start=1)
    }
    metadata_color_codes = {
        index: label
        for label, index in lba_color_codes.items()
    }

    metadata = LasGeologyMetadata(
        source="DIGITAL GEOLOG project geology",
        descriptions=descriptions,
        stratigraphy=tuple(stratigraphy),
        lba_type_codes=metadata_type_codes,
        lba_color_codes=metadata_color_codes,
    )
    return LasGeologyExportPlan(
        metadata=metadata,
        description_ids=description_ids,
        lithology_description_ids=lithology_description_ids,
        stratigraphy_codes=stratigraphy_codes,
        lba_type_codes=lba_type_codes,
        lba_color_codes=lba_color_codes,
    )


def render_las_geology_metadata_section(
    metadata: LasGeologyMetadata,
    *,
    newline: bytes = b"\n",
) -> bytes:
    """Render bounded portable geology metadata as one LAS ~Other section."""

    payload = {
        "schema_version": metadata.schema_version,
        "source": metadata.source,
        "descriptions": {
            str(key): {
                "top": item.top_depth,
                "bottom": item.bottom_depth,
                "text_ru": item.text_ru,
            }
            for key, item in sorted(metadata.descriptions.items())
        },
        "stratigraphy": [
            {
                "top": item.top_depth,
                "bottom": item.bottom_depth,
                "short": item.code,
                "name_ru": item.name_ru,
                **({"rank": item.rank} if item.rank else {}),
                **({"color": item.color} if item.color else {}),
                **(
                    {"description_ru": item.description_ru}
                    if item.description_ru
                    else {}
                ),
            }
            for item in metadata.stratigraphy
        ],
        "lba_type_codes": {
            str(key): value for key, value in sorted(metadata.lba_type_codes.items())
        },
        "lba_color_codes": {
            str(key): value for key, value in sorted(metadata.lba_color_codes.items())
        },
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(raw) > _MAX_DECOMPRESSED_BYTES:
        raise ValueError("Portable geology metadata exceeds the safe decoded size limit")
    compressed = zlib.compress(raw, 9)
    if len(compressed) > _MAX_COMPRESSED_BYTES:
        raise ValueError("Portable geology metadata exceeds the safe compressed size limit")
    encoded = base64.b64encode(compressed)
    if len(encoded) > _MAX_ENCODED_BYTES:
        raise ValueError("Portable geology metadata exceeds the safe encoded size limit")

    lines = [
        b"~Other GeoWorkbench Geology Metadata",
        b"# GEOWORKBENCH_GEOLOGY_METADATA schema=1",
    ]
    for offset in range(0, len(encoded), 72):
        prefix = (
            _PAYLOAD_PREFIX
            if offset == 0
            else _PAYLOAD_CONT_PREFIX
        )
        lines.append(prefix + encoded[offset : offset + 72])
    return newline.join(lines) + newline


def append_las_geology_metadata(
    path: str | Path,
    metadata: LasGeologyMetadata,
) -> Path:
    """Replace prior GeoWorkbench geology metadata and insert the current block."""

    target = Path(path)
    raw = target.read_bytes()
    newline = b"\r\n" if b"\r\n" in raw else b"\n"

    section_matches = list(re.finditer(rb"(?m)^[ \t]*~[^\r\n]*", raw))
    parts: list[bytes] = []
    cursor = 0
    for index, match in enumerate(section_matches):
        start = match.start()
        end = (
            section_matches[index + 1].start()
            if index + 1 < len(section_matches)
            else len(raw)
        )
        section = raw[start:end]
        if _MARKER in section:
            parts.append(raw[cursor:start])
            cursor = end
    if cursor:
        parts.append(raw[cursor:])
        raw = b"".join(parts)

    data_section = re.search(rb"(?im)^~A(?:SCII)?\b[^\r\n]*", raw)
    if data_section is None:
        raise ValueError("LAS ASCII section is missing")
    section = render_las_geology_metadata_section(metadata, newline=newline)
    offset = data_section.start()
    target.write_bytes(raw[:offset] + section + raw[offset:])
    return target


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
