from __future__ import annotations

from dataclasses import dataclass
import re
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class TimeNormalizationResult:
    values: NDArray[np.datetime64]
    datetime_format: str
    timezone: str | None
    warnings: tuple[str, ...]


_UTC_OFFSET = re.compile(r"^UTC(?P<sign>[+-])(?P<hours>\d{2}):(?P<minutes>\d{2})$")


def normalize_iso8601_strings(values: NDArray[Any]) -> TimeNormalizationResult | None:
    source = np.asarray(values)
    if source.ndim != 1 or source.dtype.kind not in {"O", "U", "S"}:
        return None
    parsed: list[datetime | None] = []
    awareness: set[bool] = set()
    offsets: set[str] = set()
    for raw in source:
        if isinstance(raw, bytes):
            try:
                text = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                return None
        else:
            text = str(raw).strip()
        if not text:
            parsed.append(None)
            continue
        try:
            value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        aware = value.utcoffset() is not None
        awareness.add(aware)
        if aware:
            offset = value.utcoffset()
            assert offset is not None
            offsets.add(_format_offset(int(offset.total_seconds())))
        parsed.append(value)
    if not any(value is not None for value in parsed):
        return None
    if len(awareness) > 1:
        return TimeNormalizationResult(
            np.full(source.shape, np.datetime64("NaT", "ns")),
            "ISO8601",
            None,
            ("смешаны значения с часовым поясом и без него",),
        )
    aware_values = awareness == {True}
    normalized = np.full(source.shape, np.datetime64("NaT", "ns"))
    for index, parsed_value in enumerate(parsed):
        if parsed_value is None:
            continue
        if aware_values:
            parsed_value = parsed_value.astimezone(timezone.utc).replace(tzinfo=None)
        normalized[index] = np.datetime64(parsed_value, "ns")
    warnings: list[str] = []
    if not aware_values:
        timezone_name = None
        warnings.append("часовой пояс отсутствует; значения не преобразованы в UTC")
    elif len(offsets) == 1:
        timezone_name = next(iter(offsets))
    else:
        timezone_name = "mixed-offset"
        warnings.append("исходные значения используют разные UTC offsets")
    if any(value is None for value in parsed):
        warnings.append("пустые значения времени сохранены как NaT")
    return TimeNormalizationResult(
        normalized,
        "ISO8601",
        timezone_name,
        tuple(warnings),
    )


def normalize_datetime_strings(
    values: NDArray[Any],
    *,
    datetime_format: str,
    timezone_name: str | None = None,
) -> TimeNormalizationResult:
    source = _string_array(values, "Колонка времени")
    if not datetime_format:
        raise ValueError("Формат даты и времени не может быть пустым")
    selected_timezone = _resolve_timezone(timezone_name)
    parsed: list[datetime | None] = []
    for row, text in enumerate(source, start=1):
        if not text:
            parsed.append(None)
            continue
        try:
            value = datetime.strptime(text, datetime_format)
        except ValueError as exc:
            raise ValueError(f"Строка {row} не соответствует формату {datetime_format}") from exc
        if value.utcoffset() is not None and selected_timezone is not None:
            raise ValueError("Формат уже содержит UTC offset; отдельный часовой пояс не нужен")
        if value.utcoffset() is None and selected_timezone is not None:
            value = _attach_timezone(value, selected_timezone, timezone_name or "UTC")
        parsed.append(value)
    return _normalize_parsed(parsed, source.shape, datetime_format, timezone_name)


def normalize_date_time_columns(
    date_values: NDArray[Any],
    time_values: NDArray[Any],
    *,
    date_format: str,
    time_format: str,
    timezone_name: str | None = None,
) -> TimeNormalizationResult:
    dates = _string_array(date_values, "Колонка DATE")
    times = _string_array(time_values, "Колонка TIME")
    if dates.shape != times.shape:
        raise ValueError("Колонки DATE и TIME должны иметь одинаковую длину")
    combined = np.array(
        [f"{date} {time}" if date and time else "" for date, time in zip(dates, times, strict=True)]
    )
    return normalize_datetime_strings(
        combined,
        datetime_format=f"{date_format} {time_format}",
        timezone_name=timezone_name,
    )


def _normalize_parsed(
    parsed: list[datetime | None],
    shape: tuple[int, ...],
    datetime_format: str,
    selected_timezone_name: str | None,
) -> TimeNormalizationResult:
    if not any(value is not None for value in parsed):
        raise ValueError("Колонка времени не содержит значений")
    awareness = {value.utcoffset() is not None for value in parsed if value is not None}
    if len(awareness) > 1:
        raise ValueError("Смешаны значения с часовым поясом и без него")
    aware = awareness == {True}
    normalized = np.full(shape, np.datetime64("NaT", "ns"))
    offsets: set[str] = set()
    for index, value in enumerate(parsed):
        if value is None:
            continue
        if aware:
            offset = value.utcoffset()
            assert offset is not None
            offsets.add(_format_offset(int(offset.total_seconds())))
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        normalized[index] = np.datetime64(value, "ns")
    warnings: list[str] = []
    if not aware:
        provenance_timezone = None
        warnings.append("часовой пояс отсутствует; значения не преобразованы в UTC")
    elif selected_timezone_name is not None:
        provenance_timezone = selected_timezone_name
    elif len(offsets) == 1:
        provenance_timezone = next(iter(offsets))
    else:
        provenance_timezone = "mixed-offset"
        warnings.append("исходные значения используют разные UTC offsets")
    if any(value is None for value in parsed):
        warnings.append("пустые DATE/TIME сохранены как NaT")
    return TimeNormalizationResult(
        normalized,
        datetime_format,
        provenance_timezone,
        tuple(warnings),
    )


def _string_array(values: NDArray[Any], label: str) -> NDArray[np.str_]:
    source = np.asarray(values)
    if source.ndim != 1 or source.dtype.kind not in {"O", "U", "S"}:
        raise ValueError(f"{label} должна быть одномерным массивом строк")
    result: list[str] = []
    for raw in source:
        if isinstance(raw, bytes):
            try:
                result.append(raw.decode("utf-8").strip())
            except UnicodeDecodeError as exc:
                raise ValueError(f"{label} содержит не-UTF-8 bytes") from exc
        else:
            result.append(str(raw).strip())
    return np.asarray(result, dtype=np.str_)


def _resolve_timezone(name: str | None) -> tzinfo | None:
    if name is None:
        return None
    normalized = name.strip()
    if not normalized:
        raise ValueError("Часовой пояс не может быть пустым")
    if normalized == "UTC":
        return timezone.utc
    match = _UTC_OFFSET.fullmatch(normalized)
    if match is not None:
        hours = int(match.group("hours"))
        minutes = int(match.group("minutes"))
        if hours > 23 or minutes > 59:
            raise ValueError("UTC offset имеет неверный диапазон")
        seconds = (hours * 60 + minutes) * 60
        if match.group("sign") == "-":
            seconds = -seconds
        return timezone(timedelta(seconds=seconds), normalized)
    try:
        return ZoneInfo(normalized)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Неизвестный часовой пояс: {normalized}") from exc


def _attach_timezone(value: datetime, selected: tzinfo, name: str) -> datetime:
    first = value.replace(tzinfo=selected, fold=0)
    second = value.replace(tzinfo=selected, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise ValueError(
            f"Локальное время {value.isoformat(sep=' ')} неоднозначно или отсутствует в зоне {name}; "
            "укажите явный UTC offset"
        )
    return first


def _format_offset(total_seconds: int) -> str:
    if total_seconds == 0:
        return "UTC"
    sign = "+" if total_seconds >= 0 else "-"
    absolute = abs(total_seconds)
    hours, remainder = divmod(absolute, 3600)
    minutes = remainder // 60
    return f"UTC{sign}{hours:02d}:{minutes:02d}"
