from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re
import struct
from typing import BinaryIO

import numpy as np

from .bundle import discover_bundle
from .decoder import codepage_name, decode_field, numeric_value
from .detector import (
    DEFAULT_MAX_PARADOX_ARRAY_BYTES,
    estimate_paradox_array_bytes,
    probe_db_format,
)
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
    retain_temporal_raw: bool = True,
    max_array_bytes: int = DEFAULT_MAX_PARADOX_ARRAY_BYTES,
) -> ParadoxTable:
    source = Path(path).expanduser().resolve()
    probe = probe_db_format(
        source,
        retain_temporal_raw=retain_temporal_raw,
        max_array_bytes=max_array_bytes,
    )
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
        table = _read_records(
            stream,
            source,
            header,
            fields,
            progress,
            cancelled,
            retain_temporal_raw=retain_temporal_raw,
            max_array_bytes=max_array_bytes,
        )
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
    if any(size == 0 for _type_code, size in pairs):
        raise ParadoxReadError("Поле Paradox не может иметь нулевой размер")
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


_PARADOX_FIELD_NAME = re.compile(r"^[^\x00-\x1f\x7f]{1,128}$")


def _parse_names(
    raw: bytes,
    start: int,
    field_count: int,
    code_page: int,
) -> tuple[list[str], str | None]:
    encoding = codepage_name(code_page)
    marker = b"".join(struct.pack("<H", ordinal) for ordinal in range(1, field_count + 1))
    marker_position = raw.find(marker, start)

    if marker_position >= 0:
        chunks = [chunk for chunk in raw[start:marker_position].split(b"\x00") if chunk]
        if len(chunks) < field_count:
            raise ParadoxReadError("В заголовке недостаточно имён полей")
        names_raw = chunks[-field_count:]
        table_candidates = chunks[:-field_count]
    else:
        # Some Paradox 7/11 tables (including GeoScape 2 Sensors.DB) do not
        # contain the optional ordinal catalogue 1..N after the field names.
        # In that case locate the contiguous run of N null-terminated printable
        # identifiers in the header.  Binary header fragments are rejected and
        # never treated as field names.
        names_raw, names_start = _find_field_name_run(
            raw,
            start=start,
            field_count=field_count,
            encoding=encoding,
        )
        table_candidates = [
            chunk for chunk in raw[start:names_start].split(b"\x00") if chunk
        ]

    names = [chunk.decode(encoding, errors="replace").strip() for chunk in names_raw]
    names = _deduplicate_names(names)
    table_name = _find_table_name(table_candidates, encoding)
    return names, table_name


def _find_field_name_run(
    raw: bytes,
    *,
    start: int,
    field_count: int,
    encoding: str,
) -> tuple[list[bytes], int]:
    chunks: list[tuple[int, bytes]] = []
    cursor = start
    while cursor < len(raw):
        end = raw.find(b"\x00", cursor)
        if end < 0:
            end = len(raw)
        chunk = raw[cursor:end]
        if chunk:
            chunks.append((cursor, chunk))
        cursor = end + 1

    runs: list[list[tuple[int, bytes]]] = []
    current: list[tuple[int, bytes]] = []
    for offset, chunk in chunks:
        if _is_field_name_chunk(chunk, encoding):
            current.append((offset, chunk))
        else:
            if len(current) >= field_count:
                runs.append(current)
            current = []
    if len(current) >= field_count:
        runs.append(current)

    if not runs:
        raise ParadoxReadError("Не найден каталог имён полей Paradox")

    # Prefer the shortest valid run and then the earliest one.  This avoids
    # consuming unrelated textual metadata after the schema while remaining
    # deterministic for malformed headers.
    runs.sort(key=lambda run: (len(run), run[0][0]))
    run = runs[0][:field_count]
    return [chunk for _offset, chunk in run], run[0][0]


def _is_field_name_chunk(chunk: bytes, encoding: str) -> bool:
    if not 1 <= len(chunk) <= 256:
        return False
    try:
        text = chunk.decode(encoding, errors="strict").strip()
    except UnicodeDecodeError:
        return False
    if not text or not _PARADOX_FIELD_NAME.fullmatch(text):
        return False
    if text.lower().endswith(".db"):
        return False
    # Require at least one alphabetic/underscore character. Pure binary
    # counters and ordinal data must not start a candidate name run.
    return any(character.isalpha() or character == "_" for character in text)


def _find_table_name(candidates: list[bytes], encoding: str) -> str | None:
    for candidate in reversed(candidates):
        match = re.search(rb"([A-Za-z][A-Za-z0-9_ .()\-]{0,259}\.db)$", candidate, re.I)
        if match is not None:
            return match.group(1).decode(encoding, errors="replace").strip()
        text = candidate.decode(encoding, errors="ignore").strip()
        if text and len(text) <= 260 and text.replace("_", "").isalnum():
            return text
    return None


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
    *,
    retain_temporal_raw: bool,
    max_array_bytes: int,
) -> ParadoxTable:
    _validate_record_allocation(
        header,
        fields,
        retain_temporal_raw=retain_temporal_raw,
        max_array_bytes=max_array_bytes,
    )

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
        if retain_temporal_raw and field.type_code in temporal_types
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
            if local_row % 64 == 0 and cancelled is not None and cancelled():
                raise ParadoxReadError("Импорт Paradox отменён пользователем")
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


def _validate_record_allocation(
    header: ParadoxHeader,
    fields: tuple[ParadoxField, ...],
    *,
    retain_temporal_raw: bool,
    max_array_bytes: int,
) -> None:
    """Reject contradictory header counts before allocating column arrays."""
    if not 1 <= header.record_size:
        raise ParadoxReadError("Некорректный размер записи Paradox")
    if not 1 <= header.max_table_size_kib <= 255:
        raise ParadoxReadError("Некорректный размер блока данных Paradox")
    if not 0 <= header.record_count <= _MAX_RECORDS:
        raise ParadoxReadError("Количество записей превышает безопасный предел")
    if not 0 <= header.file_blocks <= 0xFFFF:
        raise ParadoxReadError("Некорректное количество блоков данных Paradox")
    if header.file_blocks == 0:
        if header.record_count:
            raise ParadoxReadError(
                "В заголовке объявлены записи, но отсутствуют блоки данных"
            )
        if header.first_block or header.last_block:
            raise ParadoxReadError("Некорректные границы цепочки блоков Paradox")
    else:
        if not (
            1 <= header.first_block <= header.file_blocks
            and 1 <= header.last_block <= header.file_blocks
        ):
            raise ParadoxReadError("Некорректные границы цепочки блоков Paradox")

        records_per_block = max(
            0,
            (header.block_size - _DATA_BLOCK_HEADER_SIZE) // header.record_size,
        )
        declared_capacity = header.file_blocks * records_per_block
        if header.record_count > declared_capacity:
            raise ParadoxReadError(
                "Количество записей в заголовке превышает вместимость блоков данных: "
                f"{header.record_count} > {declared_capacity}"
            )
    if any(field.size <= 0 for field in fields):
        raise ParadoxReadError("Поле Paradox не может иметь нулевой размер")
    if max_array_bytes <= 0:
        raise ParadoxReadError("Лимит памяти Paradox должен быть положительным")
    estimated_array_bytes = estimate_paradox_array_bytes(
        header.record_count,
        tuple(field.type_code for field in fields),
        retain_temporal_raw=retain_temporal_raw,
    )
    if estimated_array_bytes > max_array_bytes:
        raise ParadoxReadError(
            "Оценочный размер массивов Paradox превышает лимит памяти: "
            f"{estimated_array_bytes} > {max_array_bytes} байт"
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
