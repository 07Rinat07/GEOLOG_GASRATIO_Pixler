from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class TimeNormalizationResult:
    values: NDArray[np.datetime64]
    datetime_format: str
    timezone: str | None
    warnings: tuple[str, ...]


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


def _format_offset(total_seconds: int) -> str:
    if total_seconds == 0:
        return "UTC"
    sign = "+" if total_seconds >= 0 else "-"
    absolute = abs(total_seconds)
    hours, remainder = divmod(absolute, 3600)
    minutes = remainder // 60
    return f"UTC{sign}{hours:02d}:{minutes:02d}"
