from __future__ import annotations

from datetime import datetime, timedelta
import math
import re
from typing import Any

import numpy as np

from geoworkbench.domain.models import CurveData, Dataset, DatasetIndex, IndexRole, IndexType

DISPLAY_DATETIME_FORMAT = "%d.%m.%Y %H:%M:%S"
_EPOCH = datetime(1970, 1, 1)
_OLE_EPOCH = datetime(1899, 12, 30)
_TIME_MNEMONICS = {
    "TIME",
    "ETIME",
    "DATETIME",
    "DATE_TIME",
    "TIMESTAMP",
    "EPOCH",
    "UNIXTIME",
    "UNIX_TIME",
    "LOGTIME",
    "S0",
}
_TIME_WORDS = ("time", "время", "уақыт", "timestamp", "date time", "дата и время")
_UTC_OFFSET = re.compile(r"^UTC(?P<sign>[+-])(?P<hours>\d{2}):(?P<minutes>\d{2})$")


def datetime64_to_datetime(value: Any) -> datetime | None:
    """Convert numpy datetime values without platform ``fromtimestamp`` calls.

    Python/Qt builds on Windows and Linux can behave differently for raw Unix
    timestamps, especially outside the C runtime range.  Conversion through an
    explicit UTC epoch is deterministic on every supported operating system.
    """

    try:
        scalar = np.datetime64(value, "ns")
    except (TypeError, ValueError, OverflowError):
        return None
    if np.isnat(scalar):
        return None
    nanoseconds = int(scalar.astype(np.int64))
    seconds, remainder = divmod(nanoseconds, 1_000_000_000)
    try:
        return _EPOCH + timedelta(seconds=seconds, microseconds=remainder // 1_000)
    except (OverflowError, ValueError):
        return None


def unix_seconds_to_datetime(value: float) -> datetime | None:
    if not isinstance(value, (int, float, np.integer, np.floating)):
        return None
    seconds = float(value)
    if not math.isfinite(seconds):
        return None
    whole, fraction = divmod(seconds, 1.0)
    try:
        return _EPOCH + timedelta(seconds=int(whole), microseconds=round(fraction * 1_000_000))
    except (OverflowError, ValueError):
        return None



def ole_automation_to_datetime(value: float) -> datetime | None:
    """Convert Delphi/OLE Automation date days without host locale/runtime calls."""

    try:
        serial = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(serial):
        return None
    try:
        return _OLE_EPOCH + timedelta(days=serial)
    except (OverflowError, ValueError):
        return None


def _format_numeric_calendar_time(
    value: float,
    *,
    unit: str | None,
    provenance: str,
    description: str,
) -> str | None:
    """Recognize persisted calendar encodings before treating a value as elapsed time."""

    normalized_unit = (unit or "").strip().casefold()
    source_text = f"{provenance} {description}".casefold()
    numeric = float(value)

    looks_ole = (
        "ole" in source_text
        or "delphi" in source_text
        or normalized_unit in {"d", "day", "days", "сут", "дн"}
    )
    if looks_ole and 1_000.0 <= numeric <= 200_000.0:
        moment = ole_automation_to_datetime(numeric)
        return moment.strftime(DISPLAY_DATETIME_FORMAT) if moment is not None else None

    looks_unix_ms = (
        "unix" in source_text
        and normalized_unit in {"ms", "msec", "millisecond", "milliseconds"}
    )
    if looks_unix_ms and abs(numeric) >= 100_000_000_000.0:
        moment = unix_seconds_to_datetime(numeric / 1_000.0)
        return moment.strftime(DISPLAY_DATETIME_FORMAT) if moment is not None else None

    looks_unix_s = "unix" in source_text or normalized_unit in {"unix", "epoch"}
    if looks_unix_s and abs(numeric) >= 100_000_000.0:
        moment = unix_seconds_to_datetime(numeric)
        return moment.strftime(DISPLAY_DATETIME_FORMAT) if moment is not None else None
    return None

def format_datetime_value(
    value: Any,
    *,
    include_milliseconds: bool = False,
    timezone_name: str | None = None,
) -> str:
    """Return invariant ``DD.MM.YYYY HH:MM:SS`` presentation.

    ``timezone_name`` is provenance only.  Dataset ``datetime64`` values are
    already normalized by the import layer; this formatter deliberately does
    not apply the host operating system timezone.
    """

    moment: datetime | None
    if isinstance(value, datetime):
        moment = value.replace(tzinfo=None)
    elif isinstance(value, (float, int, np.floating, np.integer)):
        moment = unix_seconds_to_datetime(float(value))
    else:
        moment = datetime64_to_datetime(value)
    if moment is None:
        return "—"
    rendered = moment.strftime(DISPLAY_DATETIME_FORMAT)
    if include_milliseconds and moment.microsecond:
        rendered += f".{moment.microsecond // 1_000:03d}".rstrip("0").rstrip(".")
    if timezone_name:
        normalized = timezone_name.strip()
        if normalized and normalized not in {"mixed-offset", "local"}:
            rendered += f" {normalized}"
    return rendered


def format_unix_seconds(
    value: float,
    *,
    include_milliseconds: bool = False,
    timezone_name: str | None = None,
) -> str:
    return format_datetime_value(
        float(value),
        include_milliseconds=include_milliseconds,
        timezone_name=timezone_name,
    )


def format_elapsed_time(value: float, unit: str | None = "s") -> str:
    seconds = elapsed_to_seconds(value, unit)
    if seconds is None:
        return "—"
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    whole = int(seconds)
    fraction = seconds - whole
    hours, remainder = divmod(whole, 3_600)
    minutes, sec = divmod(remainder, 60)
    rendered = f"{sign}{hours:02d}:{minutes:02d}:{sec:02d}"
    if fraction >= 0.0005:
        rendered += f".{round(fraction * 1_000):03d}".rstrip("0").rstrip(".")
    return rendered


def elapsed_to_seconds(value: float, unit: str | None) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    normalized = (unit or "s").strip().casefold()
    factors = {
        "ns": 1e-9,
        "us": 1e-6,
        "µs": 1e-6,
        "ms": 1e-3,
        "msec": 1e-3,
        "millisecond": 1e-3,
        "milliseconds": 1e-3,
        "s": 1.0,
        "sec": 1.0,
        "second": 1.0,
        "seconds": 1.0,
        "сек": 1.0,
        "min": 60.0,
        "minute": 60.0,
        "minutes": 60.0,
        "мин": 60.0,
        "h": 3_600.0,
        "hr": 3_600.0,
        "hour": 3_600.0,
        "hours": 3_600.0,
        "ч": 3_600.0,
        "d": 86_400.0,
        "day": 86_400.0,
        "days": 86_400.0,
    }
    return numeric * factors.get(normalized, 1.0)


def first_datetime_index(dataset: Dataset) -> DatasetIndex | None:
    candidates = [
        index
        for index in dataset.indexes.values()
        if index.role is IndexRole.TIME and index.index_type is IndexType.DATETIME
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.confidence)


def format_datetime_at_row(dataset: Dataset, row: int) -> str | None:
    index = first_datetime_index(dataset)
    if index is None or row < 0 or row >= index.values.size:
        return None
    rendered = format_datetime_value(
        index.values[row],
        include_milliseconds=True,
        timezone_name=index.timezone,
    )
    return None if rendered == "—" else rendered


def dataset_time_origin(dataset: Dataset) -> datetime | None:
    index = first_datetime_index(dataset)
    if index is not None:
        values = np.asarray(index.values).astype("datetime64[ns]")
        valid = values[~np.isnat(values)]
        if valid.size:
            return datetime64_to_datetime(valid[0])
    date_text = (dataset.headers.get("DATE") or dataset.parameters.get("DATE") or "").strip()
    time_text = (dataset.headers.get("TIME") or dataset.parameters.get("TIME") or "").strip()
    if not date_text:
        return None
    combined = f"{date_text} {time_text or '00:00:00'}".strip()
    normalized = combined.replace("T", " ").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None)
    except ValueError:
        pass
    for pattern in (
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ):
        try:
            return datetime.strptime(combined, pattern)
        except ValueError:
            continue
    return None


def is_time_curve(dataset: Dataset, curve: CurveData) -> bool:
    names = {
        curve.metadata.original_mnemonic.strip().upper(),
        (curve.metadata.canonical_mnemonic or "").strip().upper(),
    }
    if names & _TIME_MNEMONICS:
        return True
    raw_mnemonic = dataset.parameters.get("PARADOX_TIME_RAW_CURVE", "").strip().upper()
    if raw_mnemonic and raw_mnemonic in names:
        return True
    provenance = curve.metadata.provenance.casefold()
    if "raw-time" in provenance or provenance.endswith(":time"):
        return True
    description = (curve.metadata.description or "").casefold()
    return any(word in description for word in _TIME_WORDS)


def format_time_curve_at_row(dataset: Dataset, curve: CurveData, row: int) -> str | None:
    if not is_time_curve(dataset, curve) or row < 0 or row >= curve.values.size:
        return None
    absolute = format_datetime_at_row(dataset, row)
    if absolute is not None:
        return absolute
    value = float(curve.values[row])
    encoded_calendar = _format_numeric_calendar_time(
        value,
        unit=curve.metadata.unit,
        provenance=curve.metadata.provenance,
        description=curve.metadata.description or "",
    )
    if encoded_calendar is not None:
        return encoded_calendar
    seconds = elapsed_to_seconds(value, curve.metadata.unit)
    origin = dataset_time_origin(dataset)
    if origin is not None and seconds is not None:
        try:
            return (origin + timedelta(seconds=seconds)).strftime(DISPLAY_DATETIME_FORMAT)
        except (OverflowError, ValueError):
            pass
    return format_elapsed_time(value, curve.metadata.unit)


def format_index_at_row(dataset: Dataset, index: DatasetIndex, row: int) -> str:
    if row < 0 or row >= index.values.size:
        return "—"
    value = index.values[row]
    if index.index_type is IndexType.DATETIME:
        return format_datetime_value(
            value,
            include_milliseconds=True,
            timezone_name=index.timezone,
        )
    if index.role is IndexRole.TIME:
        absolute = format_datetime_at_row(dataset, row)
        if absolute is not None:
            return absolute
        seconds = elapsed_to_seconds(float(value), index.unit)
        origin = dataset_time_origin(dataset)
        if origin is not None and seconds is not None:
            try:
                return (origin + timedelta(seconds=seconds)).strftime(DISPLAY_DATETIME_FORMAT)
            except (OverflowError, ValueError):
                pass
        return format_elapsed_time(float(value), index.unit)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(numeric):
        return "—"
    suffix = f" {index.unit}" if index.unit else ""
    return f"{numeric:g}{suffix}"


def format_index_endpoint(index: DatasetIndex, value: Any) -> str:
    if index.index_type is IndexType.DATETIME:
        return format_datetime_value(value, include_milliseconds=True, timezone_name=index.timezone)
    if index.role is IndexRole.TIME:
        try:
            return format_elapsed_time(float(value), index.unit)
        except (TypeError, ValueError):
            return "—"
    try:
        return f"{float(value):.10g}"
    except (TypeError, ValueError):
        return str(value)
