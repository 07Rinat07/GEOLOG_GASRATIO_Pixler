"""Read-only LAS 3.0 section inventory for cautious multi-set format discovery.

This module classifies *raw source sections*, not numeric samples. A successful
inventory is not proof that LAS 3.0 channels can be imported or round-tripped.
No original LAS bytes are modified, normalized or re-serialized.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import re

from geoworkbench.data.lossless_las import read_lossless_las, section_role


_LAS3_VERSION_LINE = re.compile(rb"(?m)^[ \t]*VERS[ \t]*\.[ \t]*([^ \t\r\n:]+)")
_VERIFIED_VERSION_PATTERN = re.compile(r"3(?:\.0+)?\Z")


class Las3InventoryError(ValueError):
    """The raw file is not a safely identifiable LAS 3.0 document."""


class Las3SectionKind(StrEnum):
    VERSION = "version"
    DEFINITION = "definition"
    DATA = "data"
    METADATA = "metadata"


@dataclass(frozen=True, slots=True)
class Las3SectionInfo:
    name: str
    header: str
    kind: Las3SectionKind
    linked_definition: str | None
    offset: int
    size_bytes: int


@dataclass(frozen=True, slots=True)
class Las3SectionInventory:
    source_path: Path
    source_size_bytes: int
    source_sha256: str
    reported_version: str
    sections: tuple[Las3SectionInfo, ...]
    unresolved_definitions: tuple[str, ...]

    @property
    def data_sections(self) -> tuple[Las3SectionInfo, ...]:
        return tuple(item for item in self.sections if item.kind is Las3SectionKind.DATA)

    @property
    def is_multi_set(self) -> bool:
        return len(self.data_sections) > 1


def _section_kind(name: str) -> Las3SectionKind:
    selected = name.casefold().split("[", 1)[0]
    if section_role(selected) == "version":
        return Las3SectionKind.VERSION
    if selected.endswith("_definition"):
        return Las3SectionKind.DEFINITION
    if section_role(selected) == "ascii" or selected.endswith("_data"):
        return Las3SectionKind.DATA
    return Las3SectionKind.METADATA


def inspect_las3_sections(
    path: str | Path,
    *,
    max_bytes: int = 16 * 1024**2,
) -> Las3SectionInventory:
    """Discover section boundaries/links with a bounded, immutable source read.

    Section-set links are only inventoried, never interpreted as cross-set
    numerical or depth-domain equivalences. The caller cannot infer verified
    sample-read/edit/source-write capability from this metadata audit.
    """
    source = Path(path)
    document = read_lossless_las(source, max_bytes=max_bytes)
    version_sections = tuple(
        section for section in document.sections
        if _section_kind(section.name) is Las3SectionKind.VERSION
    )
    if len(version_sections) != 1:
        raise Las3InventoryError("LAS 3.0 requires exactly one version section")
    version_bytes = document.section_bytes(version_sections[0])
    version_lines = _LAS3_VERSION_LINE.findall(version_bytes)
    if len(version_lines) != 1:
        raise Las3InventoryError("LAS 3.0 source VERS header is missing or ambiguous")
    version = version_lines[0].decode("ascii", errors="replace")
    if _VERIFIED_VERSION_PATTERN.fullmatch(version) is None:
        raise Las3InventoryError(f"LAS version is not 3.0: {version!r}")

    sections: list[Las3SectionInfo] = []
    for section in document.sections:
        header = section.header
        _, separator, raw_link = header.partition("|")
        definition = raw_link.strip().casefold() if separator else None
        sections.append(
            Las3SectionInfo(
                name=section.name,
                header=header,
                kind=_section_kind(section.name),
                linked_definition=definition,
                offset=section.start_offset,
                size_bytes=section.end_offset - section.start_offset,
            )
        )
    known_definitions = {
        section.name.casefold()
        for section in sections
        if section.kind is Las3SectionKind.DEFINITION
    }
    unresolved = tuple(
        section.linked_definition
        for section in sections
        if section.linked_definition is not None
        and section.linked_definition not in known_definitions
    )
    return Las3SectionInventory(
        source_path=source,
        source_size_bytes=document.size_bytes,
        source_sha256=document.sha256,
        reported_version=version,
        sections=tuple(sections),
        unresolved_definitions=unresolved,
    )
