from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from geoworkbench.printing.pagination import validate_print_page_count


PRINT_SIMPLE_HEADER_MM = 7.0
PRINT_FOOTER_MM = 6.0
PRINT_VERTICAL_GAP_MM = 2.0
_MAX_AUTO_CONTENT_HEIGHT_PX = 6000
MAX_AUTOMATIC_PRINT_PAGE_COUNT = 96


@dataclass(frozen=True, slots=True)
class TabletAutoPageGeometry:
    """Resolved vertical density for one automatically filled print page."""

    units_per_page: float
    target_content_height_px: int
    page_aspect_ratio: float


@dataclass(frozen=True, slots=True)
class TabletAutoFirstPageGeometry:
    """Reduced first-page viewport required by the visible column header."""

    units_per_page: float
    target_content_height_px: int


def bounded_automatic_page_capacities(
    domain_span: float,
    *,
    first_units_per_page: float,
    regular_units_per_page: float,
    last_units_per_page: float | None = None,
    single_units_per_page: float | None = None,
    maximum_pages: int = MAX_AUTOMATIC_PRINT_PAGE_COUNT,
) -> tuple[float, float]:
    """Expand automatic intervals when the current zoom would create too many pages."""

    span = float(domain_span)
    first = float(first_units_per_page)
    regular = float(regular_units_per_page)
    if not all(value > 0.0 for value in (span, first, regular)):
        raise ValueError("Автоматические интервалы и диапазон должны быть положительными")
    last = None if last_units_per_page is None else float(last_units_per_page)
    single = None if single_units_per_page is None else float(single_units_per_page)
    if last is not None and last <= 0.0:
        raise ValueError("Интервал последней страницы должен быть положительным")
    if single is not None and single < 0.0:
        raise ValueError("Интервал одностраничного документа не может быть отрицательным")
    if isinstance(maximum_pages, bool) or not isinstance(maximum_pages, int):
        raise ValueError("Предел автоматических страниц должен быть целым числом")
    if maximum_pages < 1:
        raise ValueError("Предел автоматических страниц должен быть положительным")

    if last is None:
        remaining = max(0.0, span - first)
        page_count = 1 + int(ceil(max(0.0, remaining - 1e-9) / regular))
        available_capacity = first + max(0, maximum_pages - 1) * regular
    elif single is not None and span <= single + 1e-9:
        page_count = 1
        available_capacity = single
    else:
        remaining = max(0.0, span - first - last)
        page_count = 2 + int(ceil(max(0.0, remaining - 1e-9) / regular))
        available_capacity = (
            first
            + max(0, maximum_pages - 2) * regular
            + last
        )
    if page_count <= maximum_pages:
        return first, regular

    scale = span / available_capacity
    return first * scale, regular * scale


def printable_tablet_body_height_mm(
    content_height_mm: float,
    *,
    header_band_mm: float = PRINT_SIMPLE_HEADER_MM,
) -> float:
    """Return the physical page height available to the tablet rendering."""

    if content_height_mm <= 0 or header_band_mm < 0:
        raise ValueError("Размеры печатных полос должны быть неотрицательными")
    return max(
        1.0,
        float(content_height_mm)
        - float(header_band_mm)
        - PRINT_FOOTER_MM
        - PRINT_VERTICAL_GAP_MM,
    )


def automatic_tablet_page_geometry(
    *,
    source_width_px: int,
    source_content_height_px: int,
    header_height_px: int,
    current_span: float,
    content_width_mm: float,
    content_height_mm: float,
    header_band_mm: float = PRINT_SIMPLE_HEADER_MM,
) -> TabletAutoPageGeometry:
    """Resolve a depth interval and off-screen viewport that fill one sheet.

    A wide form is scaled to the paper width. Its live screen height is often
    too small for that horizontal scale, which leaves a narrow graph strip in
    the middle of a landscape page. Automatic mode increases the hidden print
    viewport height and the depth/time span by the same factor. Text, axes and
    grid geometry are re-rendered rather than stretched.
    """

    if source_width_px <= 0 or source_content_height_px <= 0:
        raise ValueError("Размер печатной формы должен быть положительным")
    if header_height_px < 0 or header_height_px >= source_content_height_px:
        raise ValueError("Высота шапки печатной формы задана некорректно")
    if current_span <= 0:
        raise ValueError("Текущий вертикальный интервал должен быть положительным")
    if content_width_mm <= 0 or content_height_mm <= 0:
        raise ValueError("Полезная область страницы должна быть положительной")
    if header_band_mm < 0:
        raise ValueError("Высота служебной шапки не может быть отрицательной")

    source_body_height = source_content_height_px - header_height_px
    printable_body_mm = printable_tablet_body_height_mm(
        content_height_mm,
        header_band_mm=header_band_mm,
    )
    page_aspect_ratio = content_width_mm / printable_body_mm
    required_body_height = max(
        source_body_height,
        round(source_width_px / page_aspect_ratio),
    )
    maximum_body_height = max(
        source_body_height,
        _MAX_AUTO_CONTENT_HEIGHT_PX - header_height_px,
    )
    target_body_height = min(required_body_height, maximum_body_height)
    units_per_page = float(current_span) * target_body_height / source_body_height
    return TabletAutoPageGeometry(
        units_per_page=max(float(current_span), units_per_page),
        target_content_height_px=target_body_height + header_height_px,
        page_aspect_ratio=page_aspect_ratio,
    )


def automatic_tablet_first_page_geometry(
    *,
    canonical_content_height_px: int,
    column_header_height_px: int,
    regular_units_per_page: float,
    regular_body_height_mm: float,
    first_body_height_mm: float,
) -> TabletAutoFirstPageGeometry:
    """Fit the first page at the same vertical density as continuations.

    Continuation pages hide the column/curve header, while the first page must
    include it together with the document passport. The first depth interval is
    therefore reduced, but the logical pixels per depth/time unit remain exactly
    the same as on every continuation page.
    """

    if canonical_content_height_px <= 0:
        raise ValueError("Эталонная высота печатной формы должна быть положительной")
    if column_header_height_px < 0 or column_header_height_px >= canonical_content_height_px:
        raise ValueError("Высота шапки колонок задана некорректно")
    if regular_units_per_page <= 0:
        raise ValueError("Автоматический интервал страницы должен быть положительным")
    if regular_body_height_mm <= 0 or first_body_height_mm <= 0:
        raise ValueError("Полезная высота страницы должна быть положительной")

    canonical_body_height = canonical_content_height_px - column_header_height_px
    physical_ratio = min(1.0, first_body_height_mm / regular_body_height_mm)
    # At the regular page scale, this is the total logical height that fits in
    # the first page's physical tablet band. The visible column header consumes
    # part of it; only the remaining body contributes depth/time capacity.
    first_total_height = round(canonical_body_height * physical_ratio)
    first_body_height = first_total_height - column_header_height_px
    if first_body_height <= 0:
        raise ValueError(
            "Печатные шапки не оставляют места для графика на первой странице"
        )
    first_body_height = min(canonical_body_height, first_body_height)
    first_units = (
        float(regular_units_per_page)
        * first_body_height
        / canonical_body_height
    )
    return TabletAutoFirstPageGeometry(
        units_per_page=max(1e-9, min(float(regular_units_per_page), first_units)),
        target_content_height_px=column_header_height_px + first_body_height,
    )


_MAX_SHORT_FINAL_PAGE_FRACTION = 0.35
_MAX_REBALANCED_PAGE_OVERFLOW_FRACTION = 0.03


def balanced_automatic_page_ranges(
    start: float,
    end: float,
    *,
    first_units_per_page: float,
    regular_units_per_page: float,
) -> tuple[tuple[float, float], ...]:
    """Build automatic page ranges without a nearly empty final sheet.

    A reduced first-page capacity plus fixed continuation capacity can leave a
    short residual interval. When the preceding regular pages can absorb it
    with no more than a small density change, the remaining interval is
    distributed evenly. Materially filled final pages keep their original
    capacity and scale.
    """

    lower = float(start)
    upper = float(end)
    first_capacity = float(first_units_per_page)
    regular_capacity = float(regular_units_per_page)
    if not all(value > 0.0 for value in (first_capacity, regular_capacity)):
        raise ValueError("Автоматические интервалы страниц должны быть положительными")
    if upper <= lower:
        return ((lower, upper),)

    remaining_after_first = max(0.0, upper - lower - first_capacity)
    expected_page_count = 1 + int(
        ceil(max(0.0, remaining_after_first - 1e-9) / regular_capacity)
    )
    validate_print_page_count(expected_page_count)

    ranges: list[tuple[float, float]] = []
    page_start = lower
    while page_start < upper - 1e-9:
        capacity = first_capacity if not ranges else regular_capacity
        page_end = min(upper, page_start + capacity)
        ranges.append((page_start, page_end))
        if page_end >= upper - 1e-9:
            break
        page_start = page_end

    if len(ranges) < 3:
        return tuple(ranges)
    final_span = ranges[-1][1] - ranges[-1][0]
    if final_span >= regular_capacity * _MAX_SHORT_FINAL_PAGE_FRACTION:
        return tuple(ranges)

    first_end = ranges[0][1]
    remaining_span = upper - first_end
    rebalanced_regular_count = len(ranges) - 2
    if rebalanced_regular_count < 1:
        return tuple(ranges)
    rebalanced_span = remaining_span / rebalanced_regular_count
    if rebalanced_span > regular_capacity * (
        1.0 + _MAX_REBALANCED_PAGE_OVERFLOW_FRACTION
    ):
        return tuple(ranges)

    balanced: list[tuple[float, float]] = [ranges[0]]
    page_start = first_end
    for page_index in range(rebalanced_regular_count):
        page_end = (
            upper
            if page_index == rebalanced_regular_count - 1
            else first_end + rebalanced_span * (page_index + 1)
        )
        balanced.append((page_start, page_end))
        page_start = page_end
    return tuple(balanced)


def reserved_ending_page_ranges(
    start: float,
    end: float,
    *,
    first_units_per_page: float,
    regular_units_per_page: float,
    last_units_per_page: float,
    single_units_per_page: float,
) -> tuple[tuple[float, float], ...]:
    """Build ranges while reserving the final page for a repeated form header.

    The graph, top header and repeated bottom header are all rendered at one
    horizontal scale.  Consequently the final sheet has a smaller graph
    capacity than an ordinary continuation.  Page ranges are resolved before
    painting, so the renderer never has to shrink the complete final tablet.
    """

    lower = float(start)
    upper = float(end)
    capacities = (
        float(first_units_per_page),
        float(regular_units_per_page),
        float(last_units_per_page),
        float(single_units_per_page),
    )
    if not all(value > 0.0 for value in capacities[:3]) or capacities[3] < 0.0:
        raise ValueError("Автоматические интервалы страниц должны быть положительными")
    if upper <= lower:
        return ((lower, upper),)

    total_span = upper - lower
    first_capacity, regular_capacity, last_capacity, single_capacity = capacities
    if total_span <= single_capacity + 1e-9:
        return ((lower, upper),)

    page_count = 2
    total_capacity = first_capacity + last_capacity
    while total_capacity < total_span - 1e-9:
        page_count += 1
        total_capacity += regular_capacity
    validate_print_page_count(page_count)

    page_capacities = [first_capacity]
    page_capacities.extend([regular_capacity] * max(0, page_count - 2))
    page_capacities.append(last_capacity)
    page_spans = _balanced_spans_with_capacities(total_span, page_capacities)

    ranges: list[tuple[float, float]] = []
    page_start = lower
    for index, page_span in enumerate(page_spans):
        page_end = upper if index == page_count - 1 else page_start + page_span
        ranges.append((page_start, page_end))
        page_start = page_end
    return tuple(ranges)


def _balanced_spans_with_capacities(
    total_span: float,
    capacities: list[float],
) -> tuple[float, ...]:
    """Distribute a range evenly without exceeding any page's capacity."""

    spans = [0.0] * len(capacities)
    active = set(range(len(capacities)))
    remaining = float(total_span)
    while active:
        level = remaining / len(active)
        limited = [index for index in active if capacities[index] < level - 1e-9]
        if not limited:
            for index in active:
                spans[index] = level
            break
        for index in limited:
            spans[index] = capacities[index]
            remaining -= capacities[index]
            active.remove(index)
    return tuple(spans)
