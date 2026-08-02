from __future__ import annotations

from dataclasses import dataclass


_AUTO_SIMPLE_HEADER_MM = 7.0
_AUTO_FOOTER_MM = 6.0
_AUTO_VERTICAL_GAP_MM = 2.0
_MIN_AUTO_BODY_HEIGHT_PX = 240
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
    header_band_mm: float = _AUTO_SIMPLE_HEADER_MM,
) -> float:
    """Return the physical page height available to the tablet rendering."""

    if content_height_mm <= 0 or header_band_mm < 0:
        raise ValueError("Размеры печатных полос должны быть неотрицательными")
    return max(
        1.0,
        float(content_height_mm)
        - float(header_band_mm)
        - _AUTO_FOOTER_MM
        - _AUTO_VERTICAL_GAP_MM,
    )


def automatic_tablet_page_geometry(
    *,
    source_width_px: int,
    source_content_height_px: int,
    header_height_px: int,
    current_span: float,
    content_width_mm: float,
    content_height_mm: float,
    header_band_mm: float = _AUTO_SIMPLE_HEADER_MM,
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
    """Fit the first page at the same horizontal scale as continuations.

    Continuation pages hide the column/curve header, while the first page must
    include it. The first depth interval is therefore reduced so the complete
    tablet (column header plus curves) still occupies the full A4 width instead
    of being uniformly shrunk and becoming narrower than the document header.
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
    first_total_height = round(canonical_body_height * physical_ratio)
    first_body_height = max(
        _MIN_AUTO_BODY_HEIGHT_PX,
        first_total_height - column_header_height_px,
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
