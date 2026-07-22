from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re
import struct
from typing import BinaryIO

import numpy as np

from .bundle import discover_bundle
from .decoder import codepage_name, decode_field, numeric_value
from .detector import probe_db_format
from .models import (
    IssueSeverity,
    ParadoxColumn,
    ParadoxField,
    ParadoxFieldType,
    ParadoxHeader,
    ParadoxIssue,
    ParadoxTable,
)


class ParadoxReadError(RuntimeError):
    pass


_MAX_FIELDS = 4096
_MAX_RECORDS = 100_000_000
_DATA_BLOCK_HEADER_SIZE = 6


def read_paradox(
    path: str | Path,
    *,
    progress: Callable[[str, int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> ParadoxTable:
    source = Path(path).expanduser().resolve()
    probe = probe_db_format(source)
    if not probe.is_paradox:
        if probe.format_name == "sqlite":
            raise ParadoxReadError(
                "Файл является SQLite DB, а не таблицей GeoScape/Borland Paradox. "
                "Исходный файл не был изменён."
            )
        raise ParadoxReadError(
            "Формат DB не распознан. Файл не является поддерживаемой базой "
            f"Paradox: {probe.reason}. Исходный файл не был изменён."
        )
    _notify(progress, "header", 0, 1)
    with source.open("rb") as stream:
        fixed = _read_exact(stream, 0x78, 0)
        header_size = struct.unpack_from("<H", fixed, 0x02)[0]
        stream.seek(0)
        raw_header = _read_exact(stream, header_size, 0)
        header, fields = _parse_header(raw_header)
        _notify(progress, "schema", 1, 1)
        table = _read_records(stream, source, header, fields, progress, cancelled)
    table.bundle = discover_bundle(source)
    return table


def read_header(path: str | Path) -> tuple[ParadoxHeader, tuple[ParadoxField, ...]]:
    source = Path(path).expanduser().resolve()
    probe = probe_db_format(source)
    if not probe.is_paradox:
        raise ParadoxReadError(probe.reason)
    with source.open("rb") as stream:
        fixed = _read_exact(stream, 0x78, 0)
        header_size = struct.unpack_from("<H", fixed, 0x02)[0]
        stream.seek(0)
        return _parse_header(_read_exact(stream, header_size, 0))


def _parse_header(raw: bytes) -> tuple[ParadoxHeader, tuple[ParadoxField, ...]]:
    record_size = struct.unpack_from("<H", raw, 0x00)[0]
    header_size = struct.unpack_from("<H", raw, 0x02)[0]
    file_type = raw[0x04]
    max_table_size_kib = raw[0x05]
    record_count = struct.unpack_from("<I", raw, 0x06)[0]
    file_blocks = struct.unpack_from("<H", raw, 0x0C)[0]
    first_block = struct.unpack_from("<H", raw, 0x0E)[0]
    last_block = struct.unpack_from("<H", raw, 0x10)[0]
    field_count = struct.unpack_from("<H", raw, 0x21)[0]
    file_version_id = raw[0x39]
    code_page = struct.unpack_from("<H", raw, 0x6A)[0] if len(raw) >= 0x6C else 1252
    if not 1 <= field_count <= _MAX_FIELDS:
        raise ParadoxReadError(f"Некорректное количество полей: {field_count}")
    if record_count > _MAX_RECORDS:
        raise ParadoxReadError("Количество записей превышает безопасный предел")

    schema_start = 0x78
    schema_end = schema_start + field_count * 2
    if schema_end > len(raw):
        raise ParadoxReadError("Схема полей выходит за границу заголовка")
    pairs = [(raw[schema_start + 2 * i], raw[schema_start + 2 * i + 1]) for i in range(field_count)]
    names, table_name = _parse_names(raw, schema_end, field_count, code_page)
    fields: list[ParadoxField] = []
    offset = 0
    for ordinal, ((type_code, size), name) in enumerate(zip(pairs, names, strict=True), start=1):
        fields.append(ParadoxField(ordinal, name, type_code, size, offset))
        offset += size
    if offset != record_size:
        raise ParadoxReadError(
            f"Размер записи {record_size} не совпадает с суммой полей {offset}"
        )
    return (
        ParadoxHeader(
            record_size,
            header_size,
            file_type,
            max_table_size_kib,
            record_count,
            file_blocks,
            first_block,
            last_block,
            field_count,
            file_version_id,
            code_page,
            table_name,
        ),
        tuple(fields),
    )


def _parse_names(
    raw: bytes,
    start: int,
    field_count: int,
    code_page: int,
) -> tuple[list[str], str | None]:
    marker = b"".join(struct.pack("<H", ordinal) for ordinal in range(1, field_count + 1))
    marker_position = raw.find(marker, start)
    if marker_position < 0:
        raise ParadoxReadError("Не найден каталог имён полей Paradox")
    chunks = [chunk for chunk in raw[start:marker_position].split(b"\x00") if chunk]
    if len(chunks) < field_count:
        raise ParadoxReadError("В заголовке недостаточно имён полей")
    encoding = codepage_name(code_page)
    names_raw = chunks[-field_count:]
    names = [chunk.decode(encoding, errors="replace").strip() for chunk in names_raw]
    names = _deduplicate_names(names)
    table_candidates = chunks[:-field_count]
    table_name = None
    for candidate in reversed(table_candidates):
        match = re.search(rb"([A-Z][A-Za-z0-9_ .()\-]{0,259}\.db)$", candidate)
        if match is not None:
            table_name = match.group(1).decode(encoding, errors="replace").strip()
            break
        text = candidate.decode(encoding, errors="ignore").strip()
        if text and len(text) <= 260 and text.replace("_", "").isalnum():
            table_name = text
            break
    return names, table_name


def _deduplicate_names(names: list[str]) -> list[str]:
    result: list[str] = []
    used: dict[str, int] = {}
    for position, raw_name in enumerate(names, start=1):
        base = raw_name or f"FIELD_{position}"
        key = base.casefold()
        occurrence = used.get(key, 0) + 1
        used[key] = occurrence
        result.append(base if occurrence == 1 else f"{base}_{occurrence}")
    return result


def _read_records(
    stream: BinaryIO,
    source: Path,
    header: ParadoxHeader,
    fields: tuple[ParadoxField, ...],
    progress: Callable[[str, int, int], None] | None,
    cancelled: Callable[[], bool] | None,
) -> ParadoxTable:
    # Numeric channels are allocated once at the declared record count. This
    # avoids a Python-object list plus a second full NumPy copy for large GTI
    # tables. Temporal typed fields keep a compact object-sidecar with decoded
    # date/time values; ordinary NUMBER/LONG columns retain their original
    # source numbers directly in the float array.
    numeric_values: dict[str, np.ndarray] = {
        field.name: np.full(header.record_count, np.nan, dtype=np.float64)
        for field in fields
        if field.is_numeric
    }
    object_values: dict[str, np.ndarray] = {
        field.name: np.full(header.record_count, None, dtype=object)
        for field in fields
        if not field.is_numeric
    }
    temporal_types = {
        ParadoxFieldType.DATE,
        ParadoxFieldType.TIME,
        ParadoxFieldType.TIMESTAMP,
        ParadoxFieldType.BCD,
    }
    temporal_raw: dict[str, np.ndarray] = {
        field.name: np.full(header.record_count, None, dtype=object)
        for field in fields
        if field.type_code in temporal_types
    }
    issues: list[ParadoxIssue] = []
    block_number = header.first_block
    visited: set[int] = set()
    row_number = 0
    encoding = codepage_name(header.code_page)
    while block_number:
        if cancelled is not None and cancelled():
            raise ParadoxReadError("Импорт Paradox отменён пользователем")
        if block_number in visited:
            raise ParadoxReadError(f"Обнаружен цикл в цепочке блоков: {block_number}")
        if not 1 <= block_number <= header.file_blocks:
            raise ParadoxReadError(f"Номер блока вне диапазона: {block_number}")
        visited.add(block_number)
        block_offset = header.header_size + (block_number - 1) * header.block_size
        stream.seek(block_offset)
        block_header = _read_exact(stream, _DATA_BLOCK_HEADER_SIZE, block_offset)
        next_block, _previous_block, last_record_offset = struct.unpack("<HHh", block_header)
        if last_record_offset < 0:
            record_count = 0
        else:
            record_count = last_record_offset // header.record_size + 1
        maximum = (header.block_size - _DATA_BLOCK_HEADER_SIZE) // header.record_size
        if record_count > maximum:
            raise ParadoxReadError(
                f"Блок {block_number}: количество записей {record_count} превышает {maximum}"
            )
        payload = _read_exact(
            stream,
            record_count * header.record_size,
            block_offset + _DATA_BLOCK_HEADER_SIZE,
        )
        for local_row in range(record_count):
            if row_number >= header.record_count:
                issues.append(
                    ParadoxIssue(
                        IssueSeverity.WARNING,
                        "extra-records",
                        "В блоках найдено больше записей, чем объявлено в заголовке",
                        source,
                        row_number + 1,
                        file_offset=(
                            block_offset
                            + _DATA_BLOCK_HEADER_SIZE
                            + local_row * header.record_size
                        ),
                        details={"declared": header.record_count},
                    )
                )
                break
            record_offset = local_row * header.record_size
            record = payload[record_offset : record_offset + header.record_size]
            absolute = block_offset + _DATA_BLOCK_HEADER_SIZE + record_offset
            for field in fields:
                raw_value = record[field.offset : field.offset + field.size]
                try:
                    decoded = decode_field(field, raw_value, encoding=encoding)
                except Exception as exc:  # field-local fault isolation is deliberate
                    decoded = None
                    issues.append(
                        ParadoxIssue(
                            IssueSeverity.ERROR,
                            "field-decode-error",
                            str(exc),
                            source,
                            row_number + 1,
                            field.name,
                            absolute + field.offset,
                            field.type_name,
                            {"error": str(exc), "field": field.name},
                        )
                    )
                if field.is_numeric:
                    numeric_values[field.name][row_number] = numeric_value(decoded)
                    raw_sidecar = temporal_raw.get(field.name)
                    if raw_sidecar is not None:
                        raw_sidecar[row_number] = decoded
                else:
                    object_values[field.name][row_number] = decoded
            row_number += 1
        _notify(progress, "records", min(row_number, header.record_count), header.record_count)
        block_number = next_block
        if row_number >= header.record_count:
            break

    if row_number != header.record_count:
        issues.append(
            ParadoxIssue(
                IssueSeverity.ERROR,
                "record-count-mismatch",
                f"Прочитано {row_number} записей вместо объявленных {header.record_count}",
                source,
                details={"read": row_number, "declared": header.record_count},
            )
        )
    columns: dict[str, ParadoxColumn] = {}
    for field in fields:
        if field.is_numeric:
            full = numeric_values[field.name]
            array = full if row_number == header.record_count else full[:row_number].copy()
            finite = array[np.isfinite(array)]
            raw_full = temporal_raw.get(field.name)
            raw_values = None
            if raw_full is not None:
                raw_values = (
                    raw_full
                    if row_number == header.record_count
                    else raw_full[:row_number].copy()
                )
            filled = int(finite.size)
            columns[field.name] = ParadoxColumn(
                field=field,
                values=array,
                raw_values=raw_values,
                filled_count=filled,
                null_count=int(array.size - filled),
                minimum=float(np.min(finite)) if finite.size else None,
                maximum=float(np.max(finite)) if finite.size else None,
                is_empty=not bool(finite.size),
            )
        else:
            full = object_values[field.name]
            array = full if row_number == header.record_count else full[:row_number].copy()
            nonempty_mask = np.fromiter(
                (item not in (None, "", b"") for item in array),
                dtype=bool,
                count=array.size,
            )
            filled = int(np.count_nonzero(nonempty_mask))
            columns[field.name] = ParadoxColumn(
                field=field,
                values=array,
                raw_values=None,
                filled_count=filled,
                null_count=int(array.size - filled),
                is_empty=filled == 0,
            )
    return ParadoxTable(
        source=source,
        bundle=discover_bundle(source),
        header=header,
        fields=fields,
        columns=columns,
        rows_read=row_number,
        issues=issues,
    )


def _read_exact(stream: BinaryIO, size: int, offset: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise ParadoxReadError(
            f"Обрезанный файл: ожидалось {size} байт по смещению {offset}, получено {len(data)}"
        )
    return data


def _notify(
    callback: Callable[[str, int, int], None] | None,
    phase: str,
    current: int,
    total: int,
) -> None:
    if callback is not None:
        callback(phase, current, total)
