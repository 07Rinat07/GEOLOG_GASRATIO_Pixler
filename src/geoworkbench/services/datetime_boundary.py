from __future__ import annotations

from math import isfinite
from typing import Any

import numpy as np


_UNIX_NANOSECONDS_PER_SECOND = 1_000_000_000.0


def coerce_datetime_boundary(value: Any) -> np.datetime64:
    """Normalize an ISO datetime or Unix-seconds boundary to ``datetime64[ns]``.

    Tablet viewports represent calendar time as floating-point Unix seconds,
    while datasets and report contracts persist ``datetime64`` values.  This
    helper is the single conversion boundary used by report resolution,
    pagination and Report Passport hashing.
    """

    if isinstance(value, (bool, np.bool_)):
        raise ValueError("datetime boundary cannot be boolean")

    if isinstance(value, np.datetime64):
        normalized = value.astype("datetime64[ns]")
        if np.isnat(normalized):
            raise ValueError("datetime boundary cannot be NaT")
        return normalized

    numeric: float | None = None
    if isinstance(value, (int, float, np.integer, np.floating)):
        numeric = float(value)
    else:
        text = str(value).strip()
        if not text:
            raise ValueError("datetime boundary cannot be empty")
        try:
            numeric = float(text)
        except (TypeError, ValueError, OverflowError):
            try:
                normalized = np.datetime64(text, "ns")
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"invalid datetime boundary: {value}") from exc
            if np.isnat(normalized):
                raise ValueError("datetime boundary cannot be NaT")
            return normalized

    assert numeric is not None
    if not isfinite(numeric):
        raise ValueError("datetime boundary must be finite")
    try:
        nanoseconds = round(numeric * _UNIX_NANOSECONDS_PER_SECOND)
        limits = np.iinfo(np.int64)
        if nanoseconds < limits.min or nanoseconds > limits.max:
            raise OverflowError
        normalized = np.datetime64(int(nanoseconds), "ns")
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid Unix-seconds datetime boundary: {value}") from exc
    if np.isnat(normalized):
        raise ValueError("datetime boundary cannot be NaT")
    return normalized


def datetime_boundary_text(value: Any) -> str:
    """Return a stable nanosecond ISO representation for a report boundary."""

    return str(coerce_datetime_boundary(value).astype("datetime64[ns]"))


def datetime_boundary_unix_seconds(value: Any) -> float:
    """Return the numeric Unix-seconds coordinate used by tablet rendering."""

    normalized = coerce_datetime_boundary(value)
    return float(normalized.astype(np.int64)) / _UNIX_NANOSECONDS_PER_SECOND
