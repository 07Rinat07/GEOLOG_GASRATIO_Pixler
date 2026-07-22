from __future__ import annotations

from datetime import date, datetime, time, timedelta
import codecs
from decimal import Decimal, InvalidOperation
import math
import struct
from typing import Any

from .models import ParadoxField, ParadoxFieldType


_PARADOX_DATE_EPOCH = date(1, 1, 1)
_MILLISECONDS_PER_DAY = 86_400_000


def codepage_name(code_page: int) -> str:
    aliases = {
        437: "cp437",
        850: "cp850",
        852: "cp852",
        866: "cp866",
        1250: "cp1250",
        1251: "cp1251",
        1252: "cp1252",
    }
    candidate = aliases.get(code_page, f"cp{code_page}" if code_page else "cp1252")
    try:
        codecs.lookup(candidate)
    except LookupError:
        return "cp1252"
    return candidate


def decode_field(field: ParadoxField, raw: bytes, *, encoding: str) -> Any:
    if not raw or all(byte == 0 for byte in raw):
        return None
    field_type = field.type_code
    if field_type == ParadoxFieldType.ALPHA:
        return raw.split(b"\x00", 1)[0].rstrip(b" ").decode(encoding, errors="replace")
    if field_type == ParadoxFieldType.DATE:
        days = _decode_sorted_integer(raw, signed=True)
        if days is None:
            return None
        try:
            return _PARADOX_DATE_EPOCH + timedelta(days=days - 1)
        except (OverflowError, ValueError):
            return days
    if field_type == ParadoxFieldType.SHORT:
        return _decode_sorted_integer(raw, signed=True)
    if field_type in {ParadoxFieldType.LONG, ParadoxFieldType.AUTOINCREMENT}:
        return _decode_sorted_integer(raw, signed=True)
    if field_type in {ParadoxFieldType.NUMBER, ParadoxFieldType.CURRENCY}:
        value = _decode_sorted_double(raw)
        return value if value is None or math.isfinite(value) else value
    if field_type == ParadoxFieldType.LOGICAL:
        transformed = _restore_sort_order(raw)
        if transformed is None:
            return None
        return bool(int.from_bytes(transformed, "big", signed=False))
    if field_type == ParadoxFieldType.TIME:
        milliseconds = _decode_sorted_integer(raw, signed=True)
        if milliseconds is None:
            return None
        if 0 <= milliseconds < _MILLISECONDS_PER_DAY:
            hours, remainder = divmod(milliseconds, 3_600_000)
            minutes, remainder = divmod(remainder, 60_000)
            seconds, millis = divmod(remainder, 1000)
            return time(hours, minutes, seconds, millis * 1000)
        return milliseconds
    if field_type == ParadoxFieldType.TIMESTAMP:
        value = _decode_sorted_double(raw)
        if value is None:
            return None
        # Paradox timestamp is stored in milliseconds relative to 0001-01-01.
        try:
            return datetime(1, 1, 1) + timedelta(milliseconds=value - _MILLISECONDS_PER_DAY)
        except (OverflowError, ValueError):
            return value
    if field_type == ParadoxFieldType.BCD:
        return _decode_bcd(raw)
    if field_type in {
        ParadoxFieldType.BYTES,
        ParadoxFieldType.BLOB,
        ParadoxFieldType.MEMO_BLOB,
        ParadoxFieldType.FORMATTED_MEMO,
        ParadoxFieldType.OLE,
        ParadoxFieldType.GRAPHIC,
    }:
        return bytes(raw)
    return bytes(raw)


def numeric_value(value: Any) -> float:
    if value is None:
        return math.nan
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, datetime):
        # Arithmetic is portable for pre-1970 timestamps; datetime.timestamp()
        # can raise platform-specific errors for old Paradox values on Windows.
        return (value - datetime(1970, 1, 1)).total_seconds()
    if isinstance(value, date):
        # Keep calendar dates compatible with the OLE/Delphi detector used by
        # GeoScape files rather than exposing Python's unrelated ordinal.
        return float((value - date(1899, 12, 30)).days)
    if isinstance(value, time):
        return (
            value.hour * 3600
            + value.minute * 60
            + value.second
            + value.microsecond / 1_000_000
        )
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return math.nan


def _restore_sort_order(raw: bytes) -> bytes | None:
    if not raw or all(byte == 0 for byte in raw):
        return None
    transformed = bytearray(raw)
    if transformed[0] & 0x80:
        transformed[0] &= 0x7F
    else:
        transformed = bytearray((~byte) & 0xFF for byte in transformed)
    return bytes(transformed)


def _decode_sorted_integer(raw: bytes, *, signed: bool) -> int | None:
    restored = _restore_sort_order(raw)
    if restored is None:
        return None
    return int.from_bytes(restored, "big", signed=signed)


def _decode_sorted_double(raw: bytes) -> float | None:
    restored = _restore_sort_order(raw)
    if restored is None:
        return None
    if len(restored) != 8:
        raise ValueError(f"Paradox NUMBER must be 8 bytes, got {len(restored)}")
    return struct.unpack(">d", restored)[0]


def _decode_bcd(raw: bytes) -> Decimal | bytes:
    # Paradox BCD variants differ in precision/scale placement.  Decode the
    # conventional sign/scale form when valid; preserve original bytes when it
    # is not, so a field decoder never invents a numeric value.
    if len(raw) < 2:
        return bytes(raw)
    precision = raw[0]
    scale = raw[1]
    digits: list[str] = []
    for byte in raw[2:]:
        high, low = byte >> 4, byte & 0x0F
        if high > 9 or low > 9:
            return bytes(raw)
        digits.extend((str(high), str(low)))
    if not digits:
        return Decimal(0)
    text = "".join(digits)[:precision].lstrip("0") or "0"
    if scale:
        text = text.zfill(scale + 1)
        text = f"{text[:-scale]}.{text[-scale:]}"
    try:
        return Decimal(text)
    except InvalidOperation:
        return bytes(raw)
