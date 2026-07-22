from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct


_SQLITE_MAGIC = b"SQLite format 3\x00"
_MAX_FIELDS = 4096
_MAX_RECORDS = 100_000_000
_MAX_RECORD_SIZE = 16 * 1024 * 1024
_MAX_HEADER_SIZE = 16 * 1024 * 1024
_SUPPORTED_DB_FILE_TYPES = {0, 2, 3, 4, 5, 6, 7, 8}


@dataclass(frozen=True, slots=True)
class FormatProbe:
    format_name: str
    confidence: float
    reason: str

    @property
    def is_paradox(self) -> bool:
        return self.format_name == "paradox"


def probe_db_format(path: str | Path) -> FormatProbe:
    source = Path(path)
    try:
        size = source.stat().st_size
        with source.open("rb") as stream:
            header = stream.read(0x1000)
    except OSError as exc:
        return FormatProbe("unreadable", 0.0, str(exc))
    if header.startswith(_SQLITE_MAGIC):
        return FormatProbe("sqlite", 1.0, "SQLite magic header")
    if size == 0:
        return FormatProbe("unknown", 0.0, "empty file")
    if len(header) < 0x78:
        return FormatProbe("unknown", 0.0, "header is shorter than the Paradox fixed header")

    record_size = struct.unpack_from("<H", header, 0x00)[0]
    header_size = struct.unpack_from("<H", header, 0x02)[0]
    file_type = header[0x04]
    max_table_size = header[0x05]
    record_count = struct.unpack_from("<I", header, 0x06)[0]
    file_blocks = struct.unpack_from("<H", header, 0x0C)[0]
    first_block = struct.unpack_from("<H", header, 0x0E)[0]
    last_block = struct.unpack_from("<H", header, 0x10)[0]
    field_count = struct.unpack_from("<H", header, 0x21)[0]

    failures: list[str] = []
    if not 1 <= record_size <= _MAX_RECORD_SIZE:
        failures.append("invalid record size")
    if not 0x58 <= header_size <= _MAX_HEADER_SIZE or header_size % 0x800:
        failures.append("invalid header size")
    if file_type not in _SUPPORTED_DB_FILE_TYPES:
        failures.append("unsupported Paradox file type")
    if not 1 <= max_table_size <= 255:
        failures.append("invalid data block size")
    if not 1 <= field_count <= _MAX_FIELDS:
        failures.append("invalid field count")
    if record_count > _MAX_RECORDS:
        failures.append("record count exceeds safety limit")
    if file_blocks and not (1 <= first_block <= file_blocks and 1 <= last_block <= file_blocks):
        failures.append("invalid block chain bounds")
    if 0x78 + field_count * 2 > min(header_size, len(header)):
        failures.append("field schema exceeds header")
    if record_size and field_count and 0x78 + field_count * 2 <= len(header):
        declared = sum(header[0x79 + 2 * index] for index in range(field_count))
        if declared != record_size:
            failures.append("sum of field sizes does not match record size")
    expected_minimum = header_size + file_blocks * max_table_size * 1024
    if file_blocks and size < expected_minimum:
        failures.append("file is truncated relative to declared blocks")

    if failures:
        return FormatProbe("unknown", 0.0, "; ".join(failures))
    return FormatProbe(
        "paradox",
        0.99,
        f"validated Paradox header: {field_count} fields, {record_count} records",
    )
