from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import ceil, isfinite


class PrintRangeMode(StrEnum):
    CURRENT = "current"
    FULL = "full"
    CUSTOM = "custom"
    SELECTION = "selection"


@dataclass(frozen=True, slots=True)
class PrintPaginationSettings:
    range_mode: PrintRangeMode = PrintRangeMode.CURRENT
    units_per_page: float = 50.0
    overlap: float = 0.0
    custom_start: float | None = None
    custom_end: float | None = None
    show_page_numbers: bool = True
    show_page_range: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("интервал на страницу", self.units_per_page),
            ("перекрытие страниц", self.overlap),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name.capitalize()} должен быть числом")
            if not isfinite(value):
                raise ValueError(f"{name.capitalize()} должен быть конечным числом")
        if self.units_per_page <= 0:
            raise ValueError("Интервал на страницу должен быть больше нуля")
        if self.overlap < 0 or self.overlap >= self.units_per_page:
            raise ValueError("Перекрытие должно быть неотрицательным и меньше интервала страницы")
        if not isinstance(self.show_page_numbers, bool) or not isinstance(
            self.show_page_range, bool
        ):
            raise ValueError("Параметры колонтитулов должны быть логическими")
        if self.range_mode is PrintRangeMode.CUSTOM:
            if self.custom_start is None or self.custom_end is None:
                raise ValueError("Для пользовательского диапазона укажите начало и конец")
            if not isfinite(self.custom_start) or not isfinite(self.custom_end):
                raise ValueError("Пользовательский диапазон должен содержать конечные числа")


@dataclass(frozen=True, slots=True)
class PrintPageSlice:
    start: float | None
    end: float | None
    index: int
    total: int

    @property
    def has_vertical_range(self) -> bool:
        return self.start is not None and self.end is not None


def build_page_slices(
    *,
    pagination: PrintPaginationSettings,
    current_range: tuple[float, float] | None,
    full_range: tuple[float, float] | None,
    selection_range: tuple[float, float] | None = None,
) -> tuple[PrintPageSlice, ...]:
    """Build deterministic non-empty page ranges for depth or time axes."""

    if full_range is None:
        return (PrintPageSlice(None, None, 1, 1),)
    domain_start, domain_end = sorted(map(float, full_range))
    if domain_start == domain_end:
        return (PrintPageSlice(domain_start, domain_end, 1, 1),)

    if pagination.range_mode is PrintRangeMode.CURRENT:
        selected = current_range or full_range
        start, end = sorted(map(float, selected))
        start = max(domain_start, start)
        end = min(domain_end, end)
        return (PrintPageSlice(start, end, 1, 1),)

    if pagination.range_mode is PrintRangeMode.SELECTION:
        if selection_range is None:
            raise ValueError("Выбранный интервал для печати отсутствует")
        start, end = sorted(map(float, selection_range))
        start = max(domain_start, start)
        end = min(domain_end, end)
        if start > end:
            raise ValueError("Выбранный интервал находится вне данных")
    elif pagination.range_mode is PrintRangeMode.CUSTOM:
        assert pagination.custom_start is not None
        assert pagination.custom_end is not None
        start, end = sorted((float(pagination.custom_start), float(pagination.custom_end)))
        start = max(domain_start, start)
        end = min(domain_end, end)
        if start > end:
            raise ValueError("Пользовательский диапазон находится вне данных")
    else:
        start, end = domain_start, domain_end

    span = min(float(pagination.units_per_page), end - start)
    if span <= 0:
        return (PrintPageSlice(start, end, 1, 1),)
    step = span - float(pagination.overlap)
    total = max(1, int(ceil(max(0.0, end - start - pagination.overlap) / step)))
    raw: list[tuple[float, float]] = []
    page_start = start
    for _ in range(total):
        page_end = min(end, page_start + span)
        raw.append((page_start, page_end))
        if page_end >= end:
            break
        page_start += step
    count = len(raw)
    return tuple(
        PrintPageSlice(page_start, page_end, index + 1, count)
        for index, (page_start, page_end) in enumerate(raw)
    )
