"""Source-bound, headless coalescing of *observed* WITS fluid-screening spans.

No depth/lag conversion, interpolation, reclassification or reservoir inference
takes place here. Callers supply actual coverage spans on one verified axis.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from geoworkbench.services.wits0_fluid_screening import Wits0FluidScreeningProjection
from geoworkbench.services.wits0_manual_gas_context import (
    Wits0GasContextAxis,
    validate_gas_context_query,
)


def _validate_source_axis(source_key: str, axis: Wits0GasContextAxis) -> None:
    if not isinstance(source_key, str) or not source_key.strip():
        raise ValueError("source_key must be non-empty text")
    if not isinstance(axis, Wits0GasContextAxis):
        raise ValueError("axis must be Wits0GasContextAxis")


@dataclass(frozen=True, slots=True)
class Wits0FluidScreeningSample:
    """One measured coverage span; depth is MD metres, elapsed time is seconds."""

    source_key: str
    axis: Wits0GasContextAxis
    start: float
    end: float
    sequence: int
    screening: Wits0FluidScreeningProjection

    def __post_init__(self) -> None:
        _validate_source_axis(self.source_key, self.axis)
        start = validate_gas_context_query(axis=self.axis, value=self.start)
        end = validate_gas_context_query(axis=self.axis, value=self.end)
        if end <= start:
            raise ValueError("screening coverage end must be greater than start")
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError("sequence must be a positive Python integer")
        if not isinstance(self.screening, Wits0FluidScreeningProjection):
            raise TypeError("screening must use Wits0FluidScreeningProjection")


@dataclass(frozen=True, slots=True)
class Wits0FluidScreeningInterval:
    """Adjacent source observations with identical provisional interpretation."""

    source_key: str
    axis: Wits0GasContextAxis
    start: float
    end: float
    first_sequence: int
    last_sequence: int
    screening: Wits0FluidScreeningProjection

    @property
    def sample_count(self) -> int:
        return self.last_sequence - self.first_sequence + 1


def coalesce_wits0_fluid_screening(
    samples: Iterable[Wits0FluidScreeningSample],
    *,
    source_key: str,
    axis: Wits0GasContextAxis,
) -> tuple[Wits0FluidScreeningInterval, ...]:
    """Join only touching, consecutive observations from the *same* verified source.

    An explicit source/axis contract prevents mixing acquisition sessions or
    MD with elapsed time. Gaps and skipped source sequences remain separate;
    overlap, reordering, or a foreign source/axis fail closed. Equality is exact:
    no tolerance silently fills an unobserved span.
    """

    _validate_source_axis(source_key, axis)
    intervals: list[Wits0FluidScreeningInterval] = []
    last_end: float | None = None
    last_sequence = 0
    for sample in samples:
        if not isinstance(sample, Wits0FluidScreeningSample):
            raise TypeError("samples must use Wits0FluidScreeningSample")
        if sample.source_key != source_key or sample.axis is not axis:
            raise ValueError("screening sample does not match the requested source and axis")
        if sample.sequence <= last_sequence:
            raise ValueError("screening source sequences must increase strictly")
        if last_end is not None and sample.start < last_end:
            raise ValueError("screening coverage must be ordered and non-overlapping")

        if (
            intervals
            and sample.start == last_end
            and sample.sequence == last_sequence + 1
            and sample.screening == intervals[-1].screening
        ):
            intervals[-1] = replace(
                intervals[-1],
                end=sample.end,
                last_sequence=sample.sequence,
            )
        else:
            intervals.append(
                Wits0FluidScreeningInterval(
                    source_key=source_key,
                    axis=axis,
                    start=sample.start,
                    end=sample.end,
                    first_sequence=sample.sequence,
                    last_sequence=sample.sequence,
                    screening=sample.screening,
                )
            )
        last_end = sample.end
        last_sequence = sample.sequence

    return tuple(intervals)


__all__ = [
    "Wits0FluidScreeningInterval",
    "Wits0FluidScreeningSample",
    "coalesce_wits0_fluid_screening",
]
