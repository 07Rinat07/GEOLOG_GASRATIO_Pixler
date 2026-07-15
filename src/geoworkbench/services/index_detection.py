from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import IndexRole, IndexType
from geoworkbench.services.time_normalization import normalize_iso8601_strings


_DEPTH_MNEMONICS = {
    "DEPT": IndexType.MD,
    "DEPTH": IndexType.MD,
    "MD": IndexType.MD,
    "HOLEDEPTH": IndexType.MD,
    "BITDEPTH": IndexType.MD,
    "TVD": IndexType.TVD,
    "TVDSS": IndexType.TVDSS,
}
_TIME_MNEMONICS = {
    "TIME",
    "DATETIME",
    "TIMESTAMP",
    "ETIME",
    "EPOCH",
    "UNIXTIME",
    "RECORD_TIME",
    "LOGTIME",
}
_LENGTH_UNITS = {"m", "meter", "metre", "ft", "feet"}
_TIME_UNITS = {"s", "sec", "second", "ms", "us", "ns", "min", "h", "hr"}


@dataclass(frozen=True, slots=True)
class IndexColumn:
    curve_id: str
    mnemonic: str
    unit: str | None
    description: str | None
    values: NDArray[Any]


@dataclass(frozen=True, slots=True)
class IndexCandidate:
    curve_id: str
    mnemonic: str
    index_type: IndexType
    role: IndexRole
    confidence: float
    evidence: tuple[str, ...]
    warnings: tuple[str, ...]
    datetime_format: str | None = None
    timezone: str | None = None


def detect_index_candidates(columns: Iterable[IndexColumn]) -> tuple[IndexCandidate, ...]:
    candidates = [_detect_column(column) for column in columns]
    return tuple(sorted(candidates, key=lambda candidate: candidate.confidence, reverse=True))


def _detect_column(column: IndexColumn) -> IndexCandidate:
    values = np.asarray(column.values)
    mnemonic = column.mnemonic.strip().upper().replace(" ", "")
    unit = (column.unit or "").strip().casefold()
    description = (column.description or "").casefold()
    evidence: list[str] = []
    warnings: list[str] = []
    score = 0.0
    role = IndexRole.GENERIC
    index_type = IndexType.GENERIC
    datetime_format: str | None = None
    timezone_name: str | None = None

    if mnemonic in _DEPTH_MNEMONICS:
        role = IndexRole.DEPTH
        index_type = _DEPTH_MNEMONICS[mnemonic]
        score += 0.55
        evidence.append(f"мнемоника {mnemonic} соответствует глубине")
    elif mnemonic in _TIME_MNEMONICS:
        role = IndexRole.TIME
        index_type = IndexType.RELATIVE_TIME
        score += 0.5
        evidence.append(f"мнемоника {mnemonic} соответствует времени")

    if unit in _LENGTH_UNITS:
        if role is IndexRole.GENERIC:
            role, index_type = IndexRole.DEPTH, IndexType.MD
        if role is IndexRole.DEPTH:
            score += 0.2
            evidence.append(f"единица {unit} имеет размерность длины")
        else:
            warnings.append("временная мнемоника имеет единицу длины")
    elif unit in _TIME_UNITS:
        if role is IndexRole.GENERIC:
            role, index_type = IndexRole.TIME, IndexType.RELATIVE_TIME
        if role is IndexRole.TIME:
            score += 0.2
            evidence.append(f"единица {unit} имеет размерность времени")
        else:
            warnings.append("глубинная мнемоника имеет единицу времени")

    if any(word in description for word in ("depth", "глубин")):
        if role is IndexRole.GENERIC:
            role, index_type = IndexRole.DEPTH, IndexType.MD
        if role is IndexRole.DEPTH:
            score += 0.1
            evidence.append("описание указывает на глубину")
    if any(word in description for word in ("time", "date", "врем", "дата")):
        if role is IndexRole.GENERIC:
            role, index_type = IndexRole.TIME, IndexType.RELATIVE_TIME
        if role is IndexRole.TIME:
            score += 0.1
            evidence.append("описание указывает на время")

    if np.issubdtype(values.dtype, np.datetime64):
        role, index_type = IndexRole.TIME, IndexType.DATETIME
        score = max(score, 0.85)
        evidence.append("тип значений datetime64")
        datetime_format = "datetime64[ns]"
        warnings.append("datetime64 не кодирует исходный часовой пояс")
        numeric = values.astype("datetime64[ns]").astype(np.int64).astype(np.float64)
    else:
        normalized_time = normalize_iso8601_strings(values)
        if normalized_time is not None and not any(
            "смешаны значения" in warning for warning in normalized_time.warnings
        ):
            role, index_type = IndexRole.TIME, IndexType.DATETIME
            score = max(score, 0.85)
            evidence.append("строковые значения соответствуют ISO 8601")
            warnings.extend(normalized_time.warnings)
            datetime_format = normalized_time.datetime_format
            timezone_name = normalized_time.timezone
            integer_values = normalized_time.values.astype("datetime64[ns]").astype(np.int64)
            numeric = integer_values.astype(np.float64)
            numeric[np.isnat(normalized_time.values)] = np.nan
        else:
            if normalized_time is not None:
                warnings.extend(normalized_time.warnings)
            try:
                numeric = values.astype(np.float64)
            except (TypeError, ValueError):
                warnings.append("значения не являются числовыми, datetime64 или ISO 8601")
                return IndexCandidate(
                    column.curve_id,
                    column.mnemonic,
                    index_type,
                    role,
                    min(score, 1.0),
                    tuple(evidence),
                    tuple(warnings),
                    datetime_format,
                    timezone_name,
                )

    finite = numeric[np.isfinite(numeric)]
    if finite.size < 2:
        warnings.append("недостаточно конечных значений")
    else:
        differences = np.diff(finite)
        monotonic = bool(np.all(differences >= 0) or np.all(differences <= 0))
        if monotonic:
            score += 0.1
            evidence.append("значения монотонны")
        else:
            warnings.append("значения имеют смешанное направление")
        if np.unique(finite).size == finite.size:
            score += 0.05
            evidence.append("значения уникальны")
        else:
            warnings.append("обнаружены повторяющиеся значения")
        timestamp_scale = _unix_timestamp_scale(finite)
        if role is IndexRole.TIME and timestamp_scale is not None and datetime_format is None:
            index_type = IndexType.DATETIME
            score += 0.15
            evidence.append(f"правдоподобный Unix timestamp ({timestamp_scale})")
            datetime_format = f"unix-{timestamp_scale}"
            timezone_name = "UTC"

    return IndexCandidate(
        curve_id=column.curve_id,
        mnemonic=column.mnemonic,
        index_type=index_type,
        role=role,
        confidence=min(score, 1.0),
        evidence=tuple(evidence),
        warnings=tuple(warnings),
        datetime_format=datetime_format,
        timezone=timezone_name,
    )


def _unix_timestamp_scale(values: NDArray[np.float64]) -> str | None:
    median = float(np.median(np.abs(values)))
    ranges = (
        (946_684_800, 4_102_444_800, "s"),
        (946_684_800_000, 4_102_444_800_000, "ms"),
        (946_684_800_000_000, 4_102_444_800_000_000, "us"),
        (946_684_800_000_000_000, 4_102_444_800_000_000_000, "ns"),
    )
    return next((scale for lower, upper, scale in ranges if lower <= median <= upper), None)
