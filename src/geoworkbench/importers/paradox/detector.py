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
_DATA_BLOCK_HEADER_SIZE = 6
_ARRAY_ITEM_SIZE_BYTES = 8
_TEMPORAL_RAW_FIELD_TYPES = {2, 20, 21, 23}
DEFAULT_MAX_PARADOX_ARRAY_BYTES = 2 * 1024**3


@dataclass(frozen=True, slots=True)
class FormatProbe:
    format_name: str
    confidence: float
    reason: str

    @property
    def is_paradox(self) -> bool:
        return self.format_name == "paradox"


def estimate_paradox_array_bytes(
    record_count: int,
    field_types: tuple[int, ...],
    *,
    retain_temporal_raw: bool,
) -> int:
    """Estimate the count-sized NumPy arrays created by the Paradox reader."""
    array_count = len(field_types)
    if retain_temporal_raw:
        array_count += sum(
            field_type in _TEMPORAL_RAW_FIELD_TYPES for field_type in field_types
        )
    return record_count * array_count * _ARRAY_ITEM_SIZE_BYTES


def probe_db_format(
    path: str | Path,
    *,
    retain_temporal_raw: bool = True,
    max_array_bytes: int = DEFAULT_MAX_PARADOX_ARRAY_BYTES,
) -> FormatProbe:
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
    if not file_blocks and record_count:
        failures.append("records declared without data blocks")
    if not file_blocks and (first_block or last_block):
        failures.append("invalid block chain bounds")
    if file_blocks and not (1 <= first_block <= file_blocks and 1 <= last_block <= file_blocks):
        failures.append("invalid block chain bounds")
    if record_size and max_table_size:
        records_per_block = max(
            0,
            (max_table_size * 1024 - _DATA_BLOCK_HEADER_SIZE) // record_size,
        )
        if record_count > file_blocks * records_per_block:
            failures.append("record count exceeds declared block capacity")
    schema_end = 0x78 + field_count * 2
    if schema_end > min(header_size, len(header)):
        failures.append("field schema exceeds header")
    if record_size and field_count and schema_end <= len(header):
        field_types = tuple(
            header[0x78 + 2 * index] for index in range(field_count)
        )
        field_sizes = tuple(
            header[0x79 + 2 * index] for index in range(field_count)
        )
        if any(field_size == 0 for field_size in field_sizes):
            failures.append("zero-sized field is not supported")
        declared = sum(field_sizes)
        if declared != record_size:
            failures.append("sum of field sizes does not match record size")
        estimated_array_bytes = estimate_paradox_array_bytes(
            record_count,
            field_types,
            retain_temporal_raw=retain_temporal_raw,
        )
        if max_array_bytes <= 0:
            failures.append("invalid array allocation budget")
        elif estimated_array_bytes > max_array_bytes:
            failures.append(
                "estimated column allocation exceeds memory budget: "
                f"{estimated_array_bytes} > {max_array_bytes} bytes"
            )
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
