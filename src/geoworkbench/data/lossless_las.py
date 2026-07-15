from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path


_SECTION_PATTERN = re.compile(rb"(?m)^(?:\xef\xbb\xbf)?[ \t]*~([^\r\n]*)")


class NewlineStyle(StrEnum):
    LF = "lf"
    CRLF = "crlf"
    CR = "cr"
    MIXED = "mixed"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class LasRawSection:
    header: str
    name: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class LosslessLasDocument:
    """Byte-preserving LAS source with an index of section boundaries."""

    raw_bytes: bytes
    encoding: str
    newline_style: NewlineStyle
    preamble_end: int
    sections: tuple[LasRawSection, ...]

    @property
    def size_bytes(self) -> int:
        return len(self.raw_bytes)

    @property
    def sha256(self) -> str:
        return sha256(self.raw_bytes).hexdigest()

    @property
    def preamble(self) -> bytes:
        return self.raw_bytes[: self.preamble_end]

    def section_bytes(self, section: LasRawSection) -> bytes:
        return self.raw_bytes[section.start_offset : section.end_offset]

    def to_bytes(self) -> bytes:
        return self.raw_bytes


def read_lossless_las(path: str | Path) -> LosslessLasDocument:
    return parse_lossless_las(Path(path).read_bytes())


def parse_lossless_las(raw_bytes: bytes) -> LosslessLasDocument:
    matches = list(_SECTION_PATTERN.finditer(raw_bytes))
    encoding = _detect_encoding(raw_bytes)
    sections: list[LasRawSection] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_bytes)
        header_bytes = match.group(1).strip()
        header = header_bytes.decode(encoding, errors="replace")
        sections.append(
            LasRawSection(
                header=header,
                name=_normalize_section_name(header),
                start_offset=start,
                end_offset=end,
            )
        )
    return LosslessLasDocument(
        raw_bytes=raw_bytes,
        encoding=encoding,
        newline_style=_detect_newline_style(raw_bytes),
        preamble_end=matches[0].start() if matches else len(raw_bytes),
        sections=tuple(sections),
    )


def _normalize_section_name(header: str) -> str:
    token = header.strip().split(maxsplit=1)[0] if header.strip() else ""
    return token.rstrip(".").casefold()


def _detect_encoding(raw_bytes: bytes) -> str:
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            raw_bytes.decode("cp1251")
        except UnicodeDecodeError:
            return "latin-1"
        return "cp1251"
    return "utf-8"


def _detect_newline_style(raw_bytes: bytes) -> NewlineStyle:
    crlf_count = raw_bytes.count(b"\r\n")
    lf_count = raw_bytes.count(b"\n") - crlf_count
    cr_count = raw_bytes.count(b"\r") - crlf_count
    present = sum(count > 0 for count in (crlf_count, lf_count, cr_count))
    if present == 0:
        return NewlineStyle.NONE
    if present > 1:
        return NewlineStyle.MIXED
    if crlf_count:
        return NewlineStyle.CRLF
    if lf_count:
        return NewlineStyle.LF
    return NewlineStyle.CR
