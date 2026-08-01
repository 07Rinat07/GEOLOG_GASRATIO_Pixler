from __future__ import annotations

from dataclasses import dataclass


_AUTO_SIMPLE_HEADER_MM = 7.0
_AUTO_FOOTER_MM = 6.0
_AUTO_VERTICAL_GAP_MM = 2.0
_MAX_AUTO_CONTENT_HEIGHT_PX = 6000


@dataclass(frozen=True, slots=True)
class TabletAutoPageGeometry:
    """Resolved vertical density for one automatically filled print page."""

    units_per_page: float
    target_content_height_px: int
    page_aspect_ratio: float


def automatic_tablet_page_geometry(
    *,
    source_width_px: int,
    source_content_height_px: int,
    header_height_px: int,
    current_span: float,
    content_width_mm: float,
    content_height_mm: float,
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

    source_body_height = source_content_height_px - header_height_px
    printable_body_mm = max(
        1.0,
        content_height_mm
        - _AUTO_SIMPLE_HEADER_MM
        - _AUTO_FOOTER_MM
        - _AUTO_VERTICAL_GAP_MM,
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
