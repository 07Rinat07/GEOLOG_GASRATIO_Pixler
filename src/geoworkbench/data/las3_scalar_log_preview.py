"""Strict read-only scalar pilot for an explicit LAS 3.0 Log_Data/Log_Definition pair.

This is a bounded diagnostic preview, not a general LAS 3.x importer or a writer.
Text and array fields are accounted for but NOT silently flattened into curves.
Only the explicitly linked, unwrapped, comma-delimited Log_Data set is eligible.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from math import isfinite, nan
from pathlib import Path
import re

from geoworkbench.data.las3_section_inventory import inspect_las3_sections
from geoworkbench.data.lossless_las import LasRawSection, read_lossless_las


_FIELD_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_\[\]-]*)\s*\.(\S*)")
_FORMAT_RE = re.compile(r"\{([^}]+)\}\s*$")
_HEADER_VALUE_RE = re.compile(
    rb"(?m)^[ \t]*(?P<key>WRAP|DLM|NULL)[ \t]*\.[ \t]*(?P<value>[^ \t\r\n:]+)"
)


class Las3ScalarPreviewError(ValueError):
    """An unsupported or ambiguous LAS 3.0 scalar log set was requested."""


@dataclass(frozen=True, slots=True)
class Las3ScalarField:
    mnemonic: str
    unit: str
    format_code: str


@dataclass(frozen=True, slots=True)
class Las3ScalarLogPreview:
    source_path: Path
    source_sha256: str
    index_mnemonic: str
    fields: tuple[Las3ScalarField, ...]
    scalar_samples: tuple[tuple[str, tuple[float, ...]], ...]
    excluded_fields: tuple[Las3ScalarField, ...]
    sample_count: int
    null_value: float | None

    def samples_for(self, mnemonic: str) -> tuple[float, ...]:
        for name, values in self.scalar_samples:
            if name.casefold() == mnemonic.casefold():
                return values
        raise KeyError(mnemonic)


def _header_values(source_bytes: bytes) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in _HEADER_VALUE_RE.finditer(source_bytes):
        key = match.group("key").decode("ascii")
        if key in values:
            raise Las3ScalarPreviewError(f"Duplicate {key} source header")
        values[key] = match.group("value").decode("ascii", errors="replace")
    return values


def read_las3_scalar_log_preview(
    path: str | Path,
    *,
    max_bytes: int = 16 * 1024**2,
    max_rows: int = 100_000,
) -> Las3ScalarLogPreview:
    """Read verified scalar cells from one explicitly linked LAS 3 Log_Data set.

    Non-scalar fields are returned in excluded_fields. Unknown layouts, column
    counts and unsupported types fail rather than return inaccurate petrophysics.
    The read-only original bytes are never rewritten, including vendor sections.
    """
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1:
        raise ValueError("max_rows must be a positive integer")
    inventory = inspect_las3_sections(path, max_bytes=max_bytes)
    document = read_lossless_las(path, max_bytes=max_bytes)
    if document.sha256 != inventory.source_sha256:
        raise Las3ScalarPreviewError("Source changed between inventory and read")

    sections: dict[str, list[LasRawSection]] = {
        name: [] for name in ("version", "log_definition", "log_data")
    }
    for section in document.sections:
        if section.name in sections:
            sections[section.name].append(section)
    if any(len(group) != 1 for group in sections.values()):
        raise Las3ScalarPreviewError("Expected one VERS, Log_Definition and Log_Data")
    version, definition, data = (
        sections[name][0] for name in ("version", "log_definition", "log_data")
    )
    header_values = _header_values(
        document.section_bytes(version)
        + b"\n"
        + b"\n".join(
            document.section_bytes(section)
            for section in document.sections
            if section.name in {"well", "well information"}
        )
    )
    if header_values.get("WRAP", "").upper() != "NO":
        raise Las3ScalarPreviewError("Pilot supports only WRAP=NO")
    if header_values.get("DLM", "").upper() != "COMMA":
        raise Las3ScalarPreviewError("Pilot supports only DLM=COMMA")
    if "|" not in data.header:
        raise Las3ScalarPreviewError("Log_Data must link Log_Definition")
    linked = data.header.split("|", 1)[1].strip().casefold()
    if linked != definition.name:
        raise Las3ScalarPreviewError("Log_Data links a different definition")

    fields: list[Las3ScalarField] = []
    seen: set[str] = set()
    definition_lines = document.section_bytes(definition).splitlines()
    for raw in definition_lines[1:]:
        line = raw.decode(document.encoding, errors="replace").strip()
        if not line or line.startswith("#"):
            continue
        field_match = _FIELD_RE.match(line)
        format_match = _FORMAT_RE.search(line)
        if field_match is None or format_match is None:
            raise Las3ScalarPreviewError("Unrecognized Log_Definition field")
        mnemonic, unit = field_match.group(1), field_match.group(2)
        key = mnemonic.casefold()
        if key in seen:
            raise Las3ScalarPreviewError(f"Duplicate Log_Definition mnemonic: {mnemonic}")
        seen.add(key)
        fields.append(Las3ScalarField(mnemonic, unit, format_match.group(1).upper()))
    if not fields or fields[0].mnemonic.upper() != "DEPT":
        raise Las3ScalarPreviewError("Pilot requires first field DEPT")
    if fields[0].format_code != "F":
        raise Las3ScalarPreviewError("Pilot depth field must be scalar float")

    numeric = tuple(
        field for field in fields
        if field.format_code == "F" or field.format_code.startswith("E")
    )
    excluded = tuple(
        field for field in fields if field not in numeric
    )
    arrays: dict[str, list[float]] = {field.mnemonic: [] for field in numeric}
    null_literal = header_values.get("NULL")
    try:
        null_value = float(null_literal) if null_literal is not None else None
    except ValueError as exc:
        raise Las3ScalarPreviewError("Invalid LAS source NULL header") from exc
    if null_value is not None and not isfinite(null_value):
        raise Las3ScalarPreviewError("NULL must be finite")

    sample_count = 0
    for raw in document.section_bytes(data).splitlines()[1:]:
        if not raw.strip() or raw.lstrip().startswith(b"#"):
            continue
        sample_count += 1
        if sample_count > max_rows:
            raise Las3ScalarPreviewError("LAS 3 scalar preview row cap exceeded")
        try:
            line = raw.decode(document.encoding, errors="replace")
            row = next(csv.reader([line], strict=True))
        except (UnicodeError, csv.Error) as exc:
            raise Las3ScalarPreviewError("Malformed Log_Data row") from exc
        if len(row) != len(fields):
            raise Las3ScalarPreviewError(
                f"Log_Data column mismatch: expected {len(fields)}, got {len(row)}"
            )
        for field, cell in zip(fields, row, strict=True):
            if field.mnemonic not in arrays:
                continue
            try:
                number = float(cell.strip())
            except ValueError as exc:
                raise Las3ScalarPreviewError(
                    f"Non-numeric scalar value in {field.mnemonic}"
                ) from exc
            if not isfinite(number):
                raise Las3ScalarPreviewError(
                    f"Non-finite scalar value in {field.mnemonic}"
                )
            arrays[field.mnemonic].append(
                nan if null_value is not None and number == null_value else number
            )
    if not sample_count:
        raise Las3ScalarPreviewError("Empty Log_Data set")
    return Las3ScalarLogPreview(
        source_path=Path(path),
        source_sha256=document.sha256,
        index_mnemonic=fields[0].mnemonic,
        fields=tuple(fields),
        scalar_samples=tuple(
            (field.mnemonic, tuple(arrays[field.mnemonic]))
            for field in numeric
        ),
        excluded_fields=excluded,
        sample_count=sample_count,
        null_value=null_value,
    )
