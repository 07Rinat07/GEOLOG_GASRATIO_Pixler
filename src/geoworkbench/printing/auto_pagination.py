from __future__ import annotations

from dataclasses import dataclass


PRINT_SIMPLE_HEADER_MM = 7.0
PRINT_FOOTER_MM = 6.0
PRINT_VERTICAL_GAP_MM = 2.0
_MAX_AUTO_CONTENT_HEIGHT_PX = 6000


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


_MIN_TINY_FINAL_PAGE_FRACTION = 0.12
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
    residual interval of less than one metre. When the residual is tiny and two
    regular pages can absorb it with only a small density change, the remaining
    interval is distributed evenly. Normal and materially partial final pages
    keep their original capacity and scale.
    """

    lower = float(start)
    upper = float(end)
    first_capacity = float(first_units_per_page)
    regular_capacity = float(regular_units_per_page)
    if not all(value > 0.0 for value in (first_capacity, regular_capacity)):
        raise ValueError("Автоматические интервалы страниц должны быть положительными")
    if upper <= lower:
        return ((lower, upper),)

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
    if final_span >= regular_capacity * _MIN_TINY_FINAL_PAGE_FRACTION:
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
