from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
import math

import numpy as np

from geoworkbench.importers.paradox.analysis import convert_time_values
from geoworkbench.importers.paradox.models import (
    IssueSeverity,
    ParadoxBundle,
    ParadoxColumn,
    ParadoxFieldType,
    ParadoxIssue,
    ParadoxTable,
)
from geoworkbench.importers.paradox.reader import read_paradox

from .container import (
    Gs2ContainerError,
    Gs2MultipartSummary,
    extract_gs2_tables,
    inspect_gs2,
)


class Gs2MultipartError(RuntimeError):
    """Raised when inner GS2 tables cannot form one ordered series."""


ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]


def read_gs2_multipart(
    source: str | Path,
    *,
    member_names: tuple[str, ...],
    progress: ProgressCallback | None = None,
    cancelled: CancelledCallback | None = None,
    max_rows: int = 50_000_000,
    max_output_bytes: int = 2 * 1024**3,
) -> ParadoxTable:
    """Read schema-compatible GS2 parts into one validated Paradox table."""

    source_path = Path(source).expanduser().resolve()
    manifest = inspect_gs2(source_path)
    group = _resolve_group(manifest.multipart_groups, member_names)
    if group.record_count > max_rows:
        raise Gs2MultipartError(
            f"Серия GS2 содержит слишком много строк: {group.record_count} > {max_rows}"
        )
    estimated_output_bytes = (
        group.record_count * max(1, group.field_count) * np.dtype(np.float64).itemsize
    )
    if estimated_output_bytes > max_output_bytes:
        raise Gs2MultipartError(
            "Оценочный размер объединённой серии GS2 превышает лимит памяти: "
            f"{estimated_output_bytes} > {max_output_bytes} байт"
        )
    _check_cancelled(cancelled)

    with extract_gs2_tables(
        source_path,
        group.member_names,
        progress=_extraction_progress(progress),
        cancelled=cancelled,
    ) as (paths, _manifest):
        if progress is not None:
            progress("schema", 1, 1)
        total_rows = group.record_count
        buffers: dict[str, np.ndarray] = {}
        filled: dict[str, int] = {}
        minima: dict[str, float | None] = {}
        maxima: dict[str, float | None] = {}
        issues: list[ParadoxIssue] = []
        first_fields = None
        first_header = None
        file_blocks = 0
        row_offset = 0
        previous_time: float | None = None
        expected_step: float | None = None
        time_field = next(
            (
                field_name
                for field_name in group.field_names
                if field_name.casefold() == "time"
            ),
            None,
        )

        for member_name, path in zip(group.member_names, paths, strict=True):
            _check_cancelled(cancelled)
            try:
                table = read_paradox(
                    path,
                    progress=_part_progress(
                        progress,
                        row_offset=row_offset,
                        total_rows=total_rows,
                    ),
                    cancelled=cancelled,
                    retain_temporal_raw=False,
                )
            except MemoryError as exc:
                raise Gs2MultipartError(
                    f"Недостаточно памяти для чтения части {member_name}"
                ) from exc
            if first_fields is not None and table.fields != first_fields:
                raise Gs2MultipartError(
                    f"Схема части {member_name} не совпадает с первой таблицей"
                )
            if table.rows_read + row_offset > total_rows:
                raise Gs2MultipartError(
                    f"Часть {member_name} выходит за объявленное число строк серии"
                )
            if first_fields is None:
                first_fields = table.fields
                first_header = table.header
                buffers = _allocate_buffers(table, total_rows)
                filled = {field.name: 0 for field in table.fields}
                minima = {field.name: None for field in table.fields}
                maxima = {field.name: None for field in table.fields}

            if time_field is not None:
                previous_time, expected_step = _validate_time_part(
                    table,
                    time_field,
                    source_path,
                    member_name,
                    previous_time=previous_time,
                    expected_step=expected_step,
                    issues=issues,
                    record_offset=row_offset,
                )

            stop = row_offset + table.rows_read
            for field in table.fields:
                column = table.columns[field.name]
                buffers[field.name][row_offset:stop] = column.values
                filled[field.name] += column.filled_count
                minima[field.name] = _minimum(minima[field.name], column.minimum)
                maxima[field.name] = _maximum(maxima[field.name], column.maximum)
            issues.extend(
                _relocate_issues(
                    table.issues,
                    source_path,
                    member_name,
                    record_offset=row_offset,
                )
            )
            file_blocks += table.header.file_blocks
            row_offset = stop
            del table

        if first_fields is None or first_header is None:
            raise Gs2MultipartError("Серия GS2 не содержит читаемых таблиц")
        if row_offset != total_rows:
            raise Gs2MultipartError(
                f"Прочитано {row_offset} строк серии вместо {total_rows}"
            )

        columns = {
            field.name: ParadoxColumn(
                field=field,
                values=buffers[field.name],
                raw_values=None,
                filled_count=filled[field.name],
                null_count=total_rows - filled[field.name],
                minimum=minima[field.name],
                maximum=maxima[field.name],
                is_empty=filled[field.name] == 0,
            )
            for field in first_fields
        }
        header = replace(
            first_header,
            record_count=total_rows,
            file_blocks=file_blocks,
            first_block=1 if file_blocks else 0,
            last_block=file_blocks,
            table_name=f"{group.base_name} ({len(group.member_names)} parts)",
        )
        if progress is not None:
            progress("records", total_rows, total_rows)
        return ParadoxTable(
            source=source_path,
            bundle=ParadoxBundle(main=source_path),
            header=header,
            fields=first_fields,
            columns=columns,
            rows_read=total_rows,
            issues=issues,
        )


def _resolve_group(
    groups: tuple[Gs2MultipartSummary, ...],
    member_names: tuple[str, ...],
) -> Gs2MultipartSummary:
    wanted = tuple(name.casefold() for name in member_names)
    for group in groups:
        if tuple(name.casefold() for name in group.member_names) == wanted:
            return group
    raise Gs2ContainerError(
        "Выбранные таблицы не образуют последовательную серию GS2 с одинаковой схемой"
    )


def _allocate_buffers(table: ParadoxTable, rows: int) -> dict[str, np.ndarray]:
    try:
        return {
            field.name: (
                np.full(rows, np.nan, dtype=np.float64)
                if field.is_numeric
                else np.full(rows, None, dtype=object)
            )
            for field in table.fields
        }
    except MemoryError as exc:
        raise Gs2MultipartError(
            f"Недостаточно памяти для итоговых массивов GS2 ({rows} строк)"
        ) from exc


def _extraction_progress(
    callback: ProgressCallback | None,
) -> ProgressCallback | None:
    if callback is None:
        return None

    def report(_phase: str, current: int, total: int) -> None:
        callback("header", current, total)

    return report


def _part_progress(
    callback: ProgressCallback | None,
    *,
    row_offset: int,
    total_rows: int,
) -> ProgressCallback | None:
    if callback is None:
        return None

    def report(phase: str, current: int, total: int) -> None:
        if phase == "records":
            callback(phase, min(total_rows, row_offset + current), total_rows)

    return report


def _validate_time_part(
    table: ParadoxTable,
    time_field: str,
    source: Path,
    member_name: str,
    *,
    previous_time: float | None,
    expected_step: float | None,
    issues: list[ParadoxIssue],
    record_offset: int,
) -> tuple[float | None, float | None]:
    field = next(field for field in table.fields if field.name == time_field)
    values = _time_values_in_seconds(table, time_field, field.type_code)
    finite_positions = np.flatnonzero(np.isfinite(values))
    finite = values[np.isfinite(values)]
    if not finite.size:
        raise Gs2MultipartError(f"Часть {member_name} не содержит значений TIME")
    deltas = np.diff(finite)
    if np.any(deltas <= 0):
        raise Gs2MultipartError(
            f"TIME в части {member_name} не является строго возрастающим"
        )
    positive_step = float(np.median(deltas)) if deltas.size else None
    first = float(finite[0])
    last = float(finite[-1])
    if previous_time is not None:
        gap = first - previous_time
        if gap <= 0:
            raise Gs2MultipartError(
                f"TIME частей перекрывается перед {member_name}: разница {gap:g} с"
            )
        reference_step = expected_step or positive_step or gap
        if gap > reference_step * 5.0:
            issues.append(
                ParadoxIssue(
                    IssueSeverity.WARNING,
                    "gs2-time-gap",
                    f"Между частями перед {member_name} обнаружен разрыв TIME {gap:g} с",
                    source,
                    record_number=record_offset + int(finite_positions[0]) + 1,
                    field_name=time_field,
                    details={
                        "member": member_name,
                        "gap_seconds": gap,
                        "expected_step_seconds": reference_step,
                    },
                )
            )
    if positive_step is not None and math.isfinite(positive_step):
        expected_step = (
            positive_step
            if expected_step is None
            else float(np.median((expected_step, positive_step)))
        )
    return last, expected_step


def _time_values_in_seconds(
    table: ParadoxTable,
    time_field: str,
    type_code: int,
) -> np.ndarray:
    values = np.asarray(table.columns[time_field].values, dtype=np.float64)
    if type_code == ParadoxFieldType.TIMESTAMP:
        return values
    elapsed, datetimes, representation = convert_time_values(values)
    if datetimes is not None:
        result = np.full(values.shape, np.nan, dtype=np.float64)
        valid = ~np.isnat(datetimes)
        result[valid] = (
            datetimes[valid].astype("datetime64[ns]").astype(np.int64)
            / 1_000_000_000
        )
        return result
    if representation == "relative-milliseconds":
        return values / 1000.0
    return values if representation == "relative-seconds" else elapsed


def _relocate_issues(
    issues: list[ParadoxIssue],
    source: Path,
    member_name: str,
    *,
    record_offset: int,
) -> list[ParadoxIssue]:
    return [
        replace(
            issue,
            file=source,
            file_offset=None,
            record_number=(
                issue.record_number + record_offset
                if issue.record_number is not None
                else None
            ),
            details={
                **issue.details,
                "gs2_member": member_name,
                **(
                    {"member_file_offset": issue.file_offset}
                    if issue.file_offset is not None
                    else {}
                ),
            },
        )
        for issue in issues
    ]


def _minimum(current: float | None, value: float | None) -> float | None:
    if value is None:
        return current
    return value if current is None else min(current, value)


def _maximum(current: float | None, value: float | None) -> float | None:
    if value is None:
        return current
    return value if current is None else max(current, value)


def _check_cancelled(cancelled: CancelledCallback | None) -> None:
    if cancelled is not None and cancelled():
        raise Gs2MultipartError("Импорт многочастной серии GS2 отменён пользователем")
