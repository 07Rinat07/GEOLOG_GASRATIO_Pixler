"""Portable LAS rock-code dictionaries.

The LAS standard does not define the meaning, colour, or hatch of a numeric
rock code.  This module keeps that project-specific contract in a small JSON
sidecar and can also place the same contract into an exported LAS ``~Other``
section.  The payload is deliberately ASCII-safe so it survives legacy
CP1251/CP866 LAS files and can be decoded by another program without relying
on the source application's locale.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from geoworkbench.domain.models import ProjectLithotype

if TYPE_CHECKING:
    from geoworkbench.project.session import ProjectSession


ROCK_CODE_DICTIONARY_SCHEMA = 1
_CODE_PATTERN = re.compile(r"^[1-9][0-9]{0,5}$")
_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")
_MAX_DICTIONARY_BYTES = 4 * 1024 * 1024
_MAX_ENTRIES = 100_000
_MAX_TEXT = 500
_EMBEDDED_MARKER = b"GEOWORKBENCH_ROCK_DICTIONARY"


class RockCodeDictionaryError(ValueError):
    """Raised when a portable rock-code dictionary is invalid."""


@dataclass(frozen=True, slots=True)
class RockCodeEntry:
    """One external numeric LAS code and its visual/project interpretation."""

    source_code: int
    lithotype_id: str
    code: str
    name_ru: str
    name_kk: str
    name_en: str
    category: str
    color: str
    pattern_key: str

    def __post_init__(self) -> None:
        if isinstance(self.source_code, bool) or not isinstance(self.source_code, int):
            raise RockCodeDictionaryError("source_code должен быть целым числом")
        if not 1 <= self.source_code <= 999999:
            raise RockCodeDictionaryError("source_code должен находиться в диапазоне 1–999999")
        if not _ID_PATTERN.fullmatch(self.lithotype_id):
            raise RockCodeDictionaryError("Некорректный lithotype_id")
        if self.code.strip() != self.code or not self.code or len(self.code) > 80:
            raise RockCodeDictionaryError("Некорректный отображаемый код литотипа")
        for value, label in (
            (self.name_ru, "name_ru"),
            (self.name_kk, "name_kk"),
            (self.name_en, "name_en"),
            (self.category, "category"),
            (self.pattern_key, "pattern_key"),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
                raise RockCodeDictionaryError(f"Некорректное поле {label}")
        if not _COLOR_PATTERN.fullmatch(self.color):
            raise RockCodeDictionaryError("color должен быть записан как #RRGGBB")

    @classmethod
    def from_project_lithotype(cls, record: ProjectLithotype, source_code: int) -> "RockCodeEntry":
        return cls(
            source_code=source_code,
            lithotype_id=record.lithotype_id,
            code=record.code,
            name_ru=record.name_ru,
            name_kk=record.name_kk or record.name_ru,
            name_en=record.name_en,
            category=record.category,
            color=record.color,
            pattern_key=record.pattern_key,
        )

    @classmethod
    def from_dict(cls, raw: Any) -> "RockCodeEntry":
        if not isinstance(raw, dict):
            raise RockCodeDictionaryError("Запись rock-code должна быть объектом")
        allowed = {
            "source_code", "lithotype_id", "code", "name_ru", "name_kk",
            "name_en", "category", "color", "pattern_key",
        }
        if set(raw) - allowed:
            raise RockCodeDictionaryError("Запись rock-code содержит неизвестные поля")
        raw_code = raw.get("source_code")
        if isinstance(raw_code, bool) or not isinstance(raw_code, int):
            raise RockCodeDictionaryError("source_code должен быть целым числом")
        required_text = (
            "lithotype_id", "code", "name_ru", "name_en", "category", "color", "pattern_key"
        )
        if any(not isinstance(raw.get(key), str) for key in required_text):
            raise RockCodeDictionaryError("Поля записи rock-code должны быть строками")
        raw_name_kk = raw.get("name_kk", raw["name_ru"])
        if not isinstance(raw_name_kk, str):
            raise RockCodeDictionaryError("Поле name_kk должно быть строкой")
        try:
            values = {
                "lithotype_id": raw["lithotype_id"],
                "code": raw["code"],
                "name_ru": raw["name_ru"],
                "name_kk": raw_name_kk,
                "name_en": raw["name_en"],
                "category": raw["category"],
                "color": raw["color"],
                "pattern_key": raw["pattern_key"],
            }
        except (KeyError, TypeError) as exc:
            raise RockCodeDictionaryError("Неполная запись rock-code") from exc
        return cls(source_code=raw_code, **values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RockCodeDictionary:
    """Validated, portable set of code-to-lithotype mappings."""

    name: str
    source: str
    entries: tuple[RockCodeEntry, ...]
    schema_version: int = ROCK_CODE_DICTIONARY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != ROCK_CODE_DICTIONARY_SCHEMA:
            raise RockCodeDictionaryError(
                f"Неподдерживаемая версия справочника: {self.schema_version}"
            )
        for value, label in ((self.name, "name"), (self.source, "source")):
            if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
                raise RockCodeDictionaryError(f"Некорректное поле {label}")
        if len(self.entries) > _MAX_ENTRIES:
            raise RockCodeDictionaryError("Слишком много записей справочника")
        codes = [entry.source_code for entry in self.entries]
        if len(codes) != len(set(codes)):
            raise RockCodeDictionaryError("Коды source_code должны быть уникальны")
        object.__setattr__(self, "entries", tuple(sorted(self.entries, key=lambda item: item.source_code)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "source": self.source,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_dict(cls, raw: Any) -> "RockCodeDictionary":
        if not isinstance(raw, dict):
            raise RockCodeDictionaryError("Справочник кодов должен быть объектом")
        allowed = {"schema_version", "name", "source", "entries"}
        if set(raw) - allowed:
            raise RockCodeDictionaryError("Справочник содержит неизвестные поля")
        version = raw.get("schema_version", ROCK_CODE_DICTIONARY_SCHEMA)
        name = raw.get("name")
        source = raw.get("source")
        entries = raw.get("entries")
        if not isinstance(version, int) or isinstance(version, bool):
            raise RockCodeDictionaryError("schema_version должен быть целым числом")
        if not isinstance(name, str) or not isinstance(source, str):
            raise RockCodeDictionaryError("Поля name и source должны быть строками")
        if not isinstance(entries, list):
            raise RockCodeDictionaryError("Поле entries должно быть массивом")
        dictionary = cls(
            name=name,
            source=source,
            entries=tuple(RockCodeEntry.from_dict(item) for item in entries),
            schema_version=version,
        )
        return dictionary

    @classmethod
    def from_json(cls, text: str) -> "RockCodeDictionary":
        if len(text.encode("utf-8")) > _MAX_DICTIONARY_BYTES:
            raise RockCodeDictionaryError("Файл справочника слишком большой")
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RockCodeDictionaryError("Файл справочника не является корректным JSON") from exc
        return cls.from_dict(raw)


def dictionary_from_session(
    session: "ProjectSession",
    *,
    name: str | None = None,
    source: str = "GeoWorkbench project",
) -> RockCodeDictionary:
    """Create a sidecar from all numeric project/LAS lithotype records."""

    entries: list[RockCodeEntry] = []
    seen: set[int] = set()
    for record in session.project.lithotypes.values():
        source_code = _source_code_for_record(record)
        if source_code is None or source_code in seen:
            continue
        entries.append(RockCodeEntry.from_project_lithotype(record, source_code))
        seen.add(source_code)
    return RockCodeDictionary(
        name=(name or session.project.name or "Rock code dictionary").strip(),
        source=source,
        entries=tuple(entries),
    )


def apply_dictionary(
    session: "ProjectSession",
    dictionary: RockCodeDictionary,
) -> tuple[int, int]:
    """Merge dictionary entries into a project without rewriting intervals.

    Returns ``(created, updated)``.  The stable ``las-code-N`` identity means
    existing lithology and cuttings intervals remain linked when a visual
    interpretation is imported from a colleague.
    """

    created = 0
    updated = 0
    for entry in dictionary.entries:
        identity = f"las-code-{entry.source_code}"
        record = ProjectLithotype(
            identity,
            str(entry.source_code),
            entry.name_ru,
            entry.name_en,
            entry.category,
            entry.color.lower(),
            entry.pattern_key,
            entry.name_kk,
        )
        previous = session.project.lithotypes.get(identity)
        if previous == record:
            continue
        session.project.lithotypes[identity] = record
        if previous is None:
            created += 1
        else:
            updated += 1
    if created or updated:
        session.dirty = True
    return created, updated


def append_las_dictionary(path: str | Path, dictionary: RockCodeDictionary) -> Path:
    """Append an ASCII-safe ``~Other`` dictionary section to an exported LAS."""

    target = Path(path)
    raw = target.read_bytes()
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    section = render_las_dictionary_section(dictionary, newline=newline)
    if raw and not raw.endswith((b"\n", b"\r")):
        raw += newline
    target.write_bytes(raw + section)
    return target


def dictionary_from_las_bytes(raw: bytes) -> RockCodeDictionary | None:
    """Read the last embedded dictionary from a LAS ``~Other`` section.

    Invalid or unrelated custom sections are ignored deliberately: a dictionary
    annotation must never make an otherwise readable LAS fail to open.
    """

    if not isinstance(raw, bytes) or _EMBEDDED_MARKER not in raw:
        return None
    section_matches = list(re.finditer(rb"(?m)^[ \t]*~[^\r\n]*", raw))
    for index in range(len(section_matches) - 1, -1, -1):
        start = section_matches[index].start()
        end = section_matches[index + 1].start() if index + 1 < len(section_matches) else len(raw)
        section = raw[start:end]
        if _EMBEDDED_MARKER not in section:
            continue
        chunks: list[str] = []
        for line in section.splitlines():
            if line.startswith(b"# JSON_BASE64="):
                chunks.append(line.removeprefix(b"# JSON_BASE64=").decode("ascii", errors="ignore"))
            elif line.startswith(b"# JSON_BASE64_CONT="):
                chunks.append(line.removeprefix(b"# JSON_BASE64_CONT=").decode("ascii", errors="ignore"))
        if not chunks:
            continue
        try:
            decoded = base64.b64decode("".join(chunks), validate=True).decode("ascii")
            return RockCodeDictionary.from_json(decoded)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error):
            continue
    return None


def render_las_dictionary_section(
    dictionary: RockCodeDictionary,
    *,
    newline: bytes = b"\n",
) -> bytes:
    """Render a human-discoverable marker plus a base64 JSON payload."""

    compact = json.dumps(dictionary.to_dict(), ensure_ascii=True, separators=(",", ":"))
    encoded = base64.b64encode(compact.encode("ascii")).decode("ascii")
    lines = [
        b"~Other GeoWorkbench Rock Dictionary",
        b"# GEOWORKBENCH_ROCK_DICTIONARY schema=1",
        b"# The JSON_BASE64 payload is the portable code/colour/pattern contract.",
    ]
    for offset in range(0, len(encoded), 72):
        lines.append(("# JSON_BASE64=" if offset == 0 else "# JSON_BASE64_CONT=").encode("ascii") + encoded[offset : offset + 72].encode("ascii"))
    for entry in dictionary.entries:
        lines.append(
            (
                f"# ROCK code={entry.source_code}; id={entry.lithotype_id}; "
                f"name_en={_ascii_field(entry.name_en)}; color={entry.color}; pattern={entry.pattern_key}"
            ).encode("ascii", errors="replace")
        )
    return newline.join(lines) + newline


def _source_code_for_record(record: ProjectLithotype) -> int | None:
    match = re.fullmatch(r"las-code-([1-9][0-9]{0,5})", record.lithotype_id)
    if match:
        return int(match.group(1))
    if _CODE_PATTERN.fullmatch(record.code):
        return int(record.code)
    return None


def _ascii_field(value: str) -> str:
    return value.encode("ascii", errors="replace").decode("ascii").replace(";", ",")


def load_dictionary(path: str | Path) -> RockCodeDictionary:
    target = Path(path)
    raw = target.read_bytes()
    if len(raw) > _MAX_DICTIONARY_BYTES:
        raise RockCodeDictionaryError("Файл справочника слишком большой")
    return RockCodeDictionary.from_json(raw.decode("utf-8-sig"))


def save_dictionary(path: str | Path, dictionary: RockCodeDictionary) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dictionary.to_json(), encoding="utf-8", newline="\n")
    return target
