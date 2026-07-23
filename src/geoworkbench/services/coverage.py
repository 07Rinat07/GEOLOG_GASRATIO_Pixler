from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import CurveData, Dataset


COVERAGE_SCHEMA_VERSION = 1


class CoverageSampleState(StrEnum):
    """Engineering state of one requested channel sample."""

    OBSERVED_VALUE = "observed_value"
    OBSERVED_ZERO = "observed_zero"
    MISSING_SAMPLE = "missing_sample"
    CHANNEL_UNAVAILABLE = "channel_unavailable"


class ChannelAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ChannelCoverage:
    """Deterministic coverage summary for one channel in one resolved interval."""

    channel_key: str
    mnemonic: str
    availability: ChannelAvailability
    total_count: int
    observed_count: int
    zero_count: int
    missing_count: int
    unavailable_count: int
    schema_version: int = COVERAGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != COVERAGE_SCHEMA_VERSION:
            raise ValueError("Неподдерживаемая версия coverage")
        if not self.channel_key.strip() or not self.mnemonic.strip():
            raise ValueError("Coverage требует непустые channel_key и mnemonic")
        counts = (
            self.total_count,
            self.observed_count,
            self.zero_count,
            self.missing_count,
            self.unavailable_count,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts):
            raise ValueError("Счётчики coverage должны быть неотрицательными целыми")
        if self.zero_count > self.observed_count:
            raise ValueError("zero_count не может превышать observed_count")
        if self.availability is ChannelAvailability.AVAILABLE:
            if self.unavailable_count != 0:
                raise ValueError("Доступный канал не может иметь unavailable_count")
            if self.observed_count + self.missing_count != self.total_count:
                raise ValueError("Coverage доступного канала не сходится с total_count")
        else:
            if self.observed_count or self.zero_count or self.missing_count:
                raise ValueError("Недоступный канал не может содержать отсчёты")
            if self.unavailable_count != self.total_count:
                raise ValueError("Недоступный канал должен покрывать весь интервал")

    @property
    def coverage_percent(self) -> float:
        return _percent(self.observed_count, self.total_count)

    @property
    def missing_percent(self) -> float:
        return _percent(self.missing_count, self.total_count)

    @property
    def zero_percent(self) -> float:
        return _percent(self.zero_count, self.total_count)

    @property
    def zero_percent_of_observed(self) -> float:
        return _percent(self.zero_count, self.observed_count)

    @property
    def primary_state(self) -> CoverageSampleState:
        if self.availability is ChannelAvailability.UNAVAILABLE:
            return CoverageSampleState.CHANNEL_UNAVAILABLE
        if self.observed_count == 0:
            return CoverageSampleState.MISSING_SAMPLE
        if self.zero_count == self.observed_count:
            return CoverageSampleState.OBSERVED_ZERO
        return CoverageSampleState.OBSERVED_VALUE

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "channel_key": self.channel_key,
            "mnemonic": self.mnemonic,
            "availability": self.availability.value,
            "primary_state": self.primary_state.value,
            "total_count": self.total_count,
            "observed_count": self.observed_count,
            "zero_count": self.zero_count,
            "missing_count": self.missing_count,
            "unavailable_count": self.unavailable_count,
            "coverage_percent": self.coverage_percent,
            "missing_percent": self.missing_percent,
            "zero_percent": self.zero_percent,
            "zero_percent_of_observed": self.zero_percent_of_observed,
        }


def classify_sample(value: float, *, channel_available: bool = True) -> CoverageSampleState:
    if not channel_available:
        return CoverageSampleState.CHANNEL_UNAVAILABLE
    number = float(value)
    if not np.isfinite(number):
        return CoverageSampleState.MISSING_SAMPLE
    if number == 0.0:
        return CoverageSampleState.OBSERVED_ZERO
    return CoverageSampleState.OBSERVED_VALUE


def analyze_curve_coverage(
    curve: CurveData,
    indices: NDArray[np.integer] | Iterable[int],
) -> ChannelCoverage:
    selected_indices = _indices(indices)
    values = np.asarray(curve.values, dtype=np.float64)
    if selected_indices.size and int(selected_indices.max()) >= values.size:
        raise ValueError("Индекс coverage выходит за границы кривой")
    selected = values[selected_indices]
    finite = np.isfinite(selected)
    observed = int(np.count_nonzero(finite))
    zeros = int(np.count_nonzero(finite & (selected == 0.0)))
    total = int(selected_indices.size)
    return ChannelCoverage(
        channel_key=curve.metadata.curve_id,
        mnemonic=curve.metadata.original_mnemonic,
        availability=ChannelAvailability.AVAILABLE,
        total_count=total,
        observed_count=observed,
        zero_count=zeros,
        missing_count=total - observed,
        unavailable_count=0,
    )


def unavailable_channel_coverage(
    mnemonic: str,
    total_count: int,
    *,
    channel_key: str | None = None,
) -> ChannelCoverage:
    normalized = str(mnemonic).strip()
    if not normalized:
        raise ValueError("Мнемоника недоступного канала не должна быть пустой")
    if isinstance(total_count, bool) or not isinstance(total_count, int) or total_count < 0:
        raise ValueError("total_count coverage должен быть неотрицательным целым")
    return ChannelCoverage(
        channel_key=channel_key or f"unavailable:{normalized.casefold()}",
        mnemonic=normalized,
        availability=ChannelAvailability.UNAVAILABLE,
        total_count=total_count,
        observed_count=0,
        zero_count=0,
        missing_count=0,
        unavailable_count=total_count,
    )


def analyze_dataset_coverage(
    dataset: Dataset,
    curve_ids: Iterable[str],
    indices: NDArray[np.integer] | Iterable[int],
    *,
    unavailable_mnemonics: Iterable[str] = (),
) -> tuple[ChannelCoverage, ...]:
    selected_indices = _indices(indices)
    result: list[ChannelCoverage] = []
    seen_ids: set[str] = set()
    for curve_id in curve_ids:
        if curve_id in seen_ids:
            continue
        seen_ids.add(curve_id)
        try:
            curve = dataset.curves[curve_id]
        except KeyError as exc:
            raise KeyError(f"Кривая coverage не найдена: {curve_id}") from exc
        result.append(analyze_curve_coverage(curve, selected_indices))
    seen_mnemonics: set[str] = set()
    for mnemonic in unavailable_mnemonics:
        normalized = str(mnemonic).strip()
        key = normalized.casefold()
        if not normalized or key in seen_mnemonics:
            continue
        seen_mnemonics.add(key)
        result.append(unavailable_channel_coverage(normalized, int(selected_indices.size)))
    return tuple(result)


def _indices(values: NDArray[np.integer] | Iterable[int]) -> NDArray[np.int64]:
    result = np.asarray(tuple(values) if not isinstance(values, np.ndarray) else values, dtype=np.int64)
    if result.ndim != 1:
        raise ValueError("Индексы coverage должны быть одномерными")
    if np.any(result < 0):
        raise ValueError("Индексы coverage не могут быть отрицательными")
    return result


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return 100.0 * float(numerator) / float(denominator)
